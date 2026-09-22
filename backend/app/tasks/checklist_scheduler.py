"""
Automatic daily checklist generation.

What it does
────────────
Every day at CHECKLIST_SCHEDULE_HOUR_UTC (UTC, default 01:00) this task
iterates over every active branch × every active template and creates one
Checklist per configured shift — but only if that combination doesn't
already exist for today (strict idempotency).

Why asyncio loop, not APScheduler/Celery
─────────────────────────────────────────
The project already uses the same pattern for revoked_token_cleanup.py.
A plain asyncio.sleep loop avoids adding scheduler deps, works correctly
in a single-process Docker container, and is trivially testable.

Template → Branch assignment rules
────────────────────────────────────
  template.branch_id is None  → applies to ALL active branches
  template.branch_id == N     → only branch N

Date per branch
───────────────
Each branch stores a `timezone` string (e.g. "Asia/Tashkent").  The
scheduler converts UTC "now" to the branch-local date so that a branch
in UTC+5 gets its checklists generated for *its* local tomorrow (which
is still UTC today at 01:00 UTC).

If the branch timezone is invalid/unknown, UTC is used as a fallback.

Manager association
───────────────────
`checklists.created_by_employee_id` is NOT NULL in the schema.  For
auto-generated rows the task finds the first active manager
(permission_level >= 1) whose primary or additional branch matches.  If
no manager is found, the branch/template combination is skipped and a
warning is logged — a human still needs to set up at least one manager.

Notifications
─────────────
After committing each batch, every active manager of the branch receives
a WebSocket + DB notification listing the templates that were generated.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, or_, and_

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.branch import Branch
from app.models.checklist import (
    Checklist,
    ChecklistItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
)
from app.models.employee import Employee
from app.models.role import Role
from app.routers.notifications import notify

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────────────

def _local_date_str(tz_name: str) -> str:
    """Return today's date string (YYYY-MM-DD) in *tz_name* local time."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("Unknown timezone '%s', falling back to UTC", tz_name)
        tz = timezone.utc
    return datetime.now(tz).strftime("%Y-%m-%d")


def _applicable_templates(
    templates: list[ChecklistTemplate], branch_id: int
) -> list[ChecklistTemplate]:
    """
    Filter the global template list down to the ones that apply to
    *branch_id*: either global templates (branch_id is None) or templates
    explicitly scoped to this branch.
    """
    return [
        t for t in templates
        if t.branch_id is None or t.branch_id == branch_id
    ]


async def _find_branch_manager(branch_id: int, db) -> Employee | None:
    """
    Return the first active employee with permission_level >= 1 (manager+)
    whose primary or additional branch includes *branch_id*.
    Returns None if the branch has no manager configured yet.
    """
    row = (
        await db.execute(
            select(Employee)
            .join(Role, Role.id == Employee.role_id)
            .where(
                Employee.status == "active",
                Role.permission_level >= 1,
                or_(
                    Employee.primary_branch_id == branch_id,
                    Employee.additional_branch_ids.contains([branch_id]),
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def _checklist_exists(
    template_id: int,
    branch_id: int,
    shift: str,
    date_str: str,
    db,
) -> bool:
    """True if a checklist for this exact template/branch/shift/date already exists."""
    row = (
        await db.execute(
            select(Checklist.id).where(
                and_(
                    Checklist.template_id == template_id,
                    Checklist.branch_id == branch_id,
                    Checklist.shift == shift,
                    Checklist.date == date_str,
                )
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def _create_checklist(
    tpl: ChecklistTemplate,
    tpl_items: list[ChecklistTemplateItem],
    branch_id: int,
    shift: str,
    date_str: str,
    manager: Employee,
    db,
) -> Checklist:
    """
    Insert a Checklist + all its ChecklistItems in one flush.
    Mirrors the logic in POST /checklists but without HTTP context.
    """
    now = datetime.now(timezone.utc)
    due_at = (
        now + timedelta(minutes=tpl.deadline_offset_minutes)
        if tpl.deadline_offset_minutes
        else None
    )

    cl = Checklist(
        template_id=tpl.id,
        template_name=tpl.name,
        branch_id=branch_id,
        shift=shift,
        date=date_str,
        status="open",
        started_at=now,
        due_at=due_at,
        created_by_employee_id=manager.id,
        # Denormalize the template's role scoping, same as the manual
        # POST /checklists flow, so auto-generated checklists are also
        # filtered by employee position (waiter vs cook, etc).
        role_ids=tpl.role_ids or [],
    )
    db.add(cl)
    await db.flush()  # populate cl.id

    for ti in tpl_items:
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
                # Denormalize task_type from the template item so the bot
                # knows how to prompt the employee without re-fetching templates.
                task_type=ti.task_type,
            )
        )

    return cl


# ── Core generation logic ─────────────────────────────────────────────────────

async def auto_generate_daily_checklists() -> dict[str, int]:
    """
    Generate checklists for all branch × template × shift combinations that
    don't already exist for today (in branch-local time).

    Returns a summary dict: {"created": N, "skipped": N, "no_manager": N}.
    """
    shifts: list[str] = [s.strip() for s in settings.CHECKLIST_AUTO_SHIFTS.split(",") if s.strip()]
    stats = {"created": 0, "skipped": 0, "no_manager": 0}

    async with AsyncSessionLocal() as db:
        branches: list[Branch] = (
            await db.execute(select(Branch).where(Branch.is_active == True))  # noqa: E712
        ).scalars().all()

        templates: list[ChecklistTemplate] = (
            await db.execute(
                select(ChecklistTemplate).where(ChecklistTemplate.is_active == True)  # noqa: E712
            )
        ).scalars().all()

        if not branches or not templates:
            logger.info("auto_generate: nothing to do (branches=%d, templates=%d)", len(branches), len(templates))
            return stats

        # Batch-load all template items in one query.
        tpl_ids = [t.id for t in templates]
        all_items: list[ChecklistTemplateItem] = (
            await db.execute(
                select(ChecklistTemplateItem)
                .where(ChecklistTemplateItem.template_id.in_(tpl_ids))
                .order_by(ChecklistTemplateItem.template_id, ChecklistTemplateItem.sort_order)
            )
        ).scalars().all()
        items_by_tpl: dict[int, list[ChecklistTemplateItem]] = {}
        for item in all_items:
            items_by_tpl.setdefault(item.template_id, []).append(item)

        for branch in branches:
            today_str = _local_date_str(branch.timezone)

            applicable = _applicable_templates(templates, branch.id)
            if not applicable:
                continue

            manager = await _find_branch_manager(branch.id, db)
            if not manager:
                logger.warning(
                    "auto_generate: no active manager for branch %d (%s) — skipping %d template(s) for %s",
                    branch.id, branch.name, len(applicable), today_str,
                )
                stats["no_manager"] += len(applicable) * len(shifts)
                continue

            created_names: list[str] = []

            for tpl in applicable:
                tpl_items = items_by_tpl.get(tpl.id, [])

                for shift in shifts:
                    if await _checklist_exists(tpl.id, branch.id, shift, today_str, db):
                        stats["skipped"] += 1
                        continue

                    await _create_checklist(tpl, tpl_items, branch.id, shift, today_str, manager, db)
                    stats["created"] += 1
                    created_names.append(f"{tpl.name} ({shift})")

            # Commit once per branch — keeps transactions short.
            await db.commit()

            # Notify every active manager of this branch about what was generated.
            if created_names:
                managers: list[Employee] = (
                    await db.execute(
                        select(Employee)
                        .join(Role, Role.id == Employee.role_id)
                        .where(
                            Employee.status == "active",
                            Role.permission_level >= 1,
                            or_(
                                Employee.primary_branch_id == branch.id,
                                Employee.additional_branch_ids.contains([branch.id]),
                            ),
                        )
                    )
                ).scalars().all()

                summary = ", ".join(created_names[:5])
                if len(created_names) > 5:
                    summary += f" и ещё {len(created_names) - 5}"

                for mgr in managers:
                    await notify(
                        db,
                        employee_id=mgr.id,
                        type_="checklist_auto_generated",
                        title=f"Чек-листы на {today_str} созданы автоматически",
                        message=f"{branch.name}: {summary}",
                    )

                await db.commit()

                logger.info(
                    "auto_generate: branch %d (%s) — created %d checklist(s) for %s",
                    branch.id, branch.name, len(created_names), today_str,
                )

    logger.info(
        "auto_generate done: created=%d skipped=%d no_manager=%d",
        stats["created"], stats["skipped"], stats["no_manager"],
    )
    return stats


# ── Background loop ────────────────────────────────────────────────────────────────

async def run_checklist_scheduler_loop() -> None:
    """
    Run auto_generate_daily_checklists() once per day at
    settings.CHECKLIST_SCHEDULE_HOUR_UTC (UTC).

    On startup we sleep until the *next* occurrence of that hour so we don't
    accidentally re-generate at every process restart.  After the first run
    we sleep exactly 24 hours so the UTC trigger hour stays stable.
    """
    trigger_hour = settings.CHECKLIST_SCHEDULE_HOUR_UTC

    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=trigger_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info(
            "checklist_scheduler: next auto-generation at %s UTC (in %.0f s)",
            next_run.strftime("%Y-%m-%d %H:%M"),
            wait_seconds,
        )

        try:
            await asyncio.sleep(wait_seconds)
        except asyncio.CancelledError:
            logger.info("checklist_scheduler: cancelled during sleep, shutting down")
            raise

        try:
            await auto_generate_daily_checklists()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never let a transient DB error kill the loop — log and retry tomorrow.
            logger.exception("checklist_scheduler: auto-generation failed; will retry in 24 h")

        # Sleep 24 h before recalculating the next trigger time.
        # (next_run recalculation at loop top handles DST / clock-skew drift.)
        await asyncio.sleep(24 * 3600)
