"""
Overrides GET /bot/checklists/today (registered before bot.router in main.py).

Differences from the original endpoint:
  • "today" is computed in each branch's own timezone (not server UTC);
  • scheduled checklists stay hidden until their opens_at moment.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_bot_secret
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import Checklist
from app.models.employee import Employee
from app.models.role import Role
from app.routers.bot import get_employee_by_bot_token
from app.routers.checklists import _build_out, _visible_to_role
from app.schemas.checklist import ChecklistOut

router = APIRouter(
    prefix="/bot",
    tags=["bot"],
    dependencies=[Depends(verify_bot_secret)],
)


def _local_date(tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        tz = timezone.utc
    return datetime.now(tz).strftime("%Y-%m-%d")


@router.get("/checklists/today", response_model=list[ChecklistOut])
async def list_my_checklists_today(
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    allowed = [b for b in {emp.primary_branch_id, *(emp.additional_branch_ids or [])} if b is not None]
    if not allowed:
        return []

    role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    is_manager = bool(role and role.permission_level >= 1)

    branches = (await db.execute(select(Branch).where(Branch.id.in_(allowed)))).scalars().all()
    dates = {date.today().isoformat(), *(_local_date(b.timezone) for b in branches)}
    now = datetime.now(timezone.utc)

    rows = (
        await db.execute(
            select(Checklist)
            .where(
                Checklist.branch_id.in_(allowed),
                Checklist.date.in_(dates),
                or_(Checklist.opens_at.is_(None), Checklist.opens_at <= now),
            )
            .order_by(Checklist.opens_at.nulls_first(), Checklist.id)
        )
    ).scalars().all()

    return [
        await _build_out(cl, db)
        for cl in rows
        if _visible_to_role(cl.role_ids or [], emp.role_id, is_manager)
    ]
