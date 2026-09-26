"""
Schedule-based checklist generation + Telegram open / reminder messages.

Every CHECK_INTERVAL_SECONDS:
  1. For every active schedule, create the checklist for the branch-local day
     (a bit before the window opens; hidden from employees until opens_at).
     due_at = end of the window, so the existing overdue escalation
     (manager +10 min, supervisor +30 min) works automatically.
  2. When a window opens -> Telegram message "Чек-лист открыт до HH:MM".
  3. REMINDER_MINUTES before the end, if not completed -> reminder message.

Idempotency: unique (schedule_id, date) + *_notified_at stamps.
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models.branch import Branch
from app.models.checklist import Checklist, ChecklistItem, ChecklistTemplate, ChecklistTemplateItem
from app.models.employee import Employee
from app.models.schedule import ChecklistSchedule
from app.tasks.checklist_scheduler import _find_branch_manager
from app.telegram import _send_message

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
REMINDER_MINUTES = 10
# Create the checklist this long before it opens (it stays hidden until opens_at).
CREATE_AHEAD_MINUTES = 60

_OPEN_TEXT = {
    "ru": "🔔 Чек-лист «{name}» открыт до {end}.",
    "uz": "🔔 «{name}» chek-listi ochildi, {end} gacha to'ldiring.",
    "en": "🔔 Checklist “{name}” is open until {end}.",
}
_REMINDER_TEXT = {
    "ru": "⏰ Осталось {minutes} мин: завершите чек-лист «{name}» до {end}.",
    "uz": "⏰ {minutes} daqiqa qoldi: «{name}» chek-listini {end} gacha yakunlang.",
    "en": "⏰ {minutes} min left: complete checklist “{name}” by {end}.",
}


def _tz(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        return timezone.utc


def window_bounds(day: date, start: time, end: time, tz: tzinfo) -> tuple[datetime, datetime]:
    """Return (opens_at, due_at) in UTC. A window ending <= start ends next day."""
    opens = datetime.combine(day, start, tzinfo=tz)
    due = datetime.combine(day, end, tzinfo=tz)
    if due <= opens:
        due += timedelta(days=1)
    return opens.astimezone(timezone.utc), due.astimezone(timezone.utc)


def _schedule_applies(s: ChecklistSchedule, day: date) -> bool:
    if day < s.start_date:
        return False
    if s.end_date is not None and day > s.end_date:
        return False
    return day.isoweekday() in (s.weekdays or [])


# ── 1. Generation ─────────────────────────────────────────────────────────────

async def _generate(db, now: datetime) -> int:
    rows = (
        await db.execute(
            select(ChecklistSchedule, Branch, ChecklistTemplate)
            .join(Branch, Branch.id == ChecklistSchedule.branch_id)
            .join(ChecklistTemplate, ChecklistTemplate.id == ChecklistSchedule.template_id)
            .where(
                ChecklistSchedule.is_active == True,  # noqa: E712
                Branch.is_active == True,  # noqa: E712
                ChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
    ).all()

    created = 0
    items_cache: dict[int, list[ChecklistTemplateItem]] = {}

    for sched, branch, tpl in rows:
        tz = _tz(branch.timezone)
        local_today = now.astimezone(tz).date()
        # Check today and tomorrow so windows just after midnight are pre-created.
        for day in (local_today, local_today + timedelta(days=1)):
            if not _schedule_applies(sched, day):
                continue
            opens_at, due_at = window_bounds(day, sched.window_start, sched.window_end, tz)
            if now < opens_at - timedelta(minutes=CREATE_AHEAD_MINUTES) or now >= due_at:
                continue

            date_str = day.isoformat()
            exists = (
                await db.execute(
                    select(Checklist.id).where(
                        and_(Checklist.schedule_id == sched.id, Checklist.date == date_str)
                    )
                )
            ).scalar_one_or_none()
            if exists:
                continue

            creator_id = sched.created_by_employee_id
            if creator_id is None:
                manager = await _find_branch_manager(branch.id, db)
                if manager is None:
                    logger.warning("schedule %d: no manager for branch %d, skipping", sched.id, branch.id)
                    continue
                creator_id = manager.id

            if tpl.id not in items_cache:
                items_cache[tpl.id] = list(
                    (
                        await db.execute(
                            select(ChecklistTemplateItem)
                            .where(ChecklistTemplateItem.template_id == tpl.id)
                            .order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.id)
                        )
                    ).scalars().all()
                )

            cl = Checklist(
                template_id=tpl.id,
                template_name=tpl.name,
                branch_id=branch.id,
                shift=sched.shift,
                date=date_str,
                status="open",
                started_at=opens_at,
                due_at=due_at,
                opens_at=opens_at,
                schedule_id=sched.id,
                created_by_employee_id=creator_id,
                role_ids=tpl.role_ids or [],
            )
            db.add(cl)
            await db.flush()
            for ti in items_cache[tpl.id]:
                db.add(
                    ChecklistItem(
                        checklist_id=cl.id,
                        title=ti.title,
                        title_uz=ti.title_uz,
                        title_en=ti.title_en,
                        description=ti.description,
                        description_uz=ti.description_uz,
                        description_en=ti.description_en,
                        sort_order=ti.sort_order,
                        is_required=ti.is_required,
                        standard_code=ti.standard_code,
                        requires_photo=ti.requires_photo,
                        requires_comment=ti.requires_comment,
                        task_type=ti.task_type or "checkbox",
                    )
                )
            await db.commit()
            created += 1
            logger.info("schedule %d: created checklist %d for %s", sched.id, cl.id, date_str)
    return created


# ── 2/3. Telegram notifications ───────────────────────────────────────────────

async def _recipients(cl: Checklist, db) -> list[Employee]:
    q = select(Employee).where(
        Employee.status == "active",
        Employee.telegram_id.isnot(None),
        or_(
            Employee.primary_branch_id == cl.branch_id,
            Employee.additional_branch_ids.contains([cl.branch_id]),
        ),
    )
    if cl.role_ids:
        q = q.where(Employee.role_id.in_(cl.role_ids))
    return list((await db.execute(q)).scalars().all())


async def _broadcast(cl: Checklist, texts: dict[str, str], tz: tzinfo, db) -> None:
    end = cl.due_at.astimezone(tz).strftime("%H:%M") if cl.due_at else "—"
    for emp in await _recipients(cl, db):
        template = texts.get(emp.preferred_language or "ru") or texts["ru"]
        text = template.format(name=cl.template_name, end=end, minutes=REMINDER_MINUTES)
        await _send_message(emp.telegram_id, text)


async def _notify(db, now: datetime) -> None:
    rows = (
        await db.execute(
            select(Checklist, Branch)
            .join(Branch, Branch.id == Checklist.branch_id)
            .where(
                Checklist.schedule_id.isnot(None),
                Checklist.status == "open",
                Checklist.opens_at <= now,
                Checklist.due_at > now,
                or_(Checklist.open_notified_at.is_(None), Checklist.reminder_notified_at.is_(None)),
            )
        )
    ).all()

    reminder_delta = timedelta(minutes=REMINDER_MINUTES)
    for cl, branch in rows:
        tz = _tz(branch.timezone)
        send_open = cl.open_notified_at is None
        send_reminder = cl.reminder_notified_at is None and cl.due_at - reminder_delta <= now
        if not (send_open or send_reminder):
            continue
        # Stamp first and commit, so a crash never produces duplicate messages.
        if send_open:
            cl.open_notified_at = now
        if send_reminder:
            cl.reminder_notified_at = now
        await db.commit()

        if send_reminder:
            # If we are already inside the reminder window, one reminder is enough.
            await _broadcast(cl, _REMINDER_TEXT, tz, db)
        elif send_open:
            await _broadcast(cl, _OPEN_TEXT, tz, db)


async def run_schedule_tick() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _generate(db, now)
        await _notify(db, now)


async def run_schedule_generator_loop() -> None:
    logger.info("schedule_generator: starting loop (interval=%d s)", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await run_schedule_tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("schedule_generator: tick failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
