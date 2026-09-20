"""
Overdue checklist escalation scheduler.

What it does
────────────
Every OVERDUE_CHECK_INTERVAL_SECONDS (default 60 s) this task scans all
open checklists whose due_at has passed and sends escalation notifications:

  • +OVERDUE_MANAGER_NOTIFY_MINUTES  (default 10 min after due_at)
    → notify every active manager (permission_level == 1) of the branch.
    type_="checklist_overdue"

  • +OVERDUE_SUPERVISOR_NOTIFY_MINUTES  (default 30 min after due_at)
    → notify every active supervisor / director (permission_level >= 2) of the branch.
    type_="checklist_escalation"

Idempotency
───────────
Two nullable timestamp columns on the Checklist row track whether each
notification wave has already been dispatched
(overdue_manager_notified_at / overdue_supervisor_notified_at).
The task sets them atomically in the same commit that inserts the
Notification rows, so restarts and crashes are safe — no duplicate alerts.

Why asyncio loop, not APScheduler/Celery
─────────────────────────────────────────
Consistent with the existing checklist_scheduler.py and
revoked_token_cleanup.py patterns: no extra scheduler deps, works
correctly in a single-process Docker container.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, or_

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.checklist import Checklist
from app.models.employee import Employee
from app.models.role import Role
from app.routers.notifications import notify

logger = logging.getLogger(__name__)


async def _get_branch_employees_by_level(
    branch_id: int,
    min_level: int,
    max_level: int | None,
    db,
) -> list[Employee]:
    """
    Return active employees assigned to *branch_id* whose role
    permission_level is in [min_level, max_level] (max_level=None means no upper bound).
    """
    q = (
        select(Employee)
        .join(Role, Role.id == Employee.role_id)
        .where(
            Employee.status == "active",
            Role.permission_level >= min_level,
            or_(
                Employee.primary_branch_id == branch_id,
                Employee.additional_branch_ids.contains([branch_id]),
            ),
        )
    )
    if max_level is not None:
        q = q.where(Role.permission_level <= max_level)
    return (await db.execute(q)).scalars().all()


async def _run_escalation_check() -> None:
    """
    Single pass: find all overdue open checklists and dispatch any
    pending escalation notification waves.
    """
    now = datetime.now(timezone.utc)
    # Thresholds: time at which each wave should fire relative to due_at.
    manager_threshold = now - timedelta(minutes=settings.OVERDUE_MANAGER_NOTIFY_MINUTES)
    supervisor_threshold = now - timedelta(minutes=settings.OVERDUE_SUPERVISOR_NOTIFY_MINUTES)

    async with AsyncSessionLocal() as db:
        # Fetch all open checklists that are overdue and still have at
        # least one notification wave pending.
        overdue: list[Checklist] = (
            await db.execute(
                select(Checklist).where(
                    and_(
                        Checklist.status == "open",
                        Checklist.due_at.isnot(None),
                        Checklist.due_at < now,
                        or_(
                            Checklist.overdue_manager_notified_at.is_(None),
                            Checklist.overdue_supervisor_notified_at.is_(None),
                        ),
                    )
                )
            )
        ).scalars().all()

        if not overdue:
            return

        logger.debug(
            "escalation_check: %d overdue checklist(s) to evaluate", len(overdue)
        )

        for cl in overdue:
            # ── Wave 1: Manager notification ──────────────────────────────────
            # Fires OVERDUE_MANAGER_NOTIFY_MINUTES after due_at.
            if (
                cl.overdue_manager_notified_at is None
                and cl.due_at <= manager_threshold
            ):
                managers = await _get_branch_employees_by_level(
                    branch_id=cl.branch_id,
                    min_level=1,
                    max_level=1,
                    db=db,
                )
                if managers:
                    for mgr in managers:
                        await notify(
                            db,
                            employee_id=mgr.id,
                            type_="checklist_overdue",
                            title=f"Чек-лист просрочен: {cl.template_name}",
                            message=(
                                f"Чек-лист \u00ab{cl.template_name}\u00bb"
                                f" (смена: {cl.shift}, дата: {cl.date})"
                                f" не выполнен в срок. Требуется вмешательство."
                            ),
                        )
                    logger.info(
                        "escalation: checklist %d — manager wave sent to %d employee(s)",
                        cl.id,
                        len(managers),
                    )
                else:
                    logger.warning(
                        "escalation: checklist %d — no managers found for branch %d; skipping wave 1",
                        cl.id,
                        cl.branch_id,
                    )
                # Always stamp the column so we don't retry on every tick.
                cl.overdue_manager_notified_at = now

            # ── Wave 2: Supervisor escalation ─────────────────────────────────
            # Fires OVERDUE_SUPERVISOR_NOTIFY_MINUTES after due_at.
            if (
                cl.overdue_supervisor_notified_at is None
                and cl.due_at <= supervisor_threshold
            ):
                supervisors = await _get_branch_employees_by_level(
                    branch_id=cl.branch_id,
                    min_level=2,
                    max_level=None,
                    db=db,
                )
                if supervisors:
                    overdue_min = int(
                        (now - cl.due_at).total_seconds() // 60
                    )
                    for sup in supervisors:
                        await notify(
                            db,
                            employee_id=sup.id,
                            type_="checklist_escalation",
                            title=f"Эскалация: чек-лист не выполнен — {cl.template_name}",
                            message=(
                                f"Чек-лист \u00ab{cl.template_name}\u00bb"
                                f" (смена: {cl.shift}, дата: {cl.date})"
                                f" просрочен на {overdue_min} мин."
                                f" Менеджер не устранил нарушение."
                                f" Требуется контроль управляющего."
                            ),
                        )
                    logger.info(
                        "escalation: checklist %d — supervisor wave sent to %d employee(s)",
                        cl.id,
                        len(supervisors),
                    )
                else:
                    logger.warning(
                        "escalation: checklist %d — no supervisors found for branch %d; skipping wave 2",
                        cl.id,
                        cl.branch_id,
                    )
                cl.overdue_supervisor_notified_at = now

        await db.commit()


async def run_overdue_escalation_loop() -> None:
    """
    Run _run_escalation_check() every OVERDUE_CHECK_INTERVAL_SECONDS seconds.

    Designed to run as a long-lived background asyncio task alongside the
    revoked_token_cleanup and checklist_scheduler loops.
    The loop starts immediately (no initial sleep) so that overdue checklists
    that existed before a restart are caught quickly.
    """
    interval = settings.OVERDUE_CHECK_INTERVAL_SECONDS
    logger.info(
        "overdue_escalation: starting loop "
        "(interval=%d s, manager_wave=%d min, supervisor_wave=%d min)",
        interval,
        settings.OVERDUE_MANAGER_NOTIFY_MINUTES,
        settings.OVERDUE_SUPERVISOR_NOTIFY_MINUTES,
    )

    while True:
        try:
            await _run_escalation_check()
        except asyncio.CancelledError:
            logger.info("overdue_escalation: cancelled, shutting down")
            raise
        except Exception:
            logger.exception(
                "overdue_escalation: check failed; will retry in %d s", interval
            )

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("overdue_escalation: cancelled during sleep, shutting down")
            raise
