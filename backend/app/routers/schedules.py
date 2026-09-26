"""CRUD for recurring checklist schedules (section «Расписание»)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import ChecklistTemplate
from app.models.employee import Employee
from app.models.schedule import ChecklistSchedule
from app.routers.audit_logs import log_action
from app.routers.checklists import _allowed_branch_ids
from app.schemas.schedule import ScheduleBase, ScheduleCreate, ScheduleOut, ScheduleUpdate

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _validate(data: ScheduleBase) -> list[int]:
    weekdays = sorted({d for d in data.weekdays})
    if not weekdays or any(d < 1 or d > 7 for d in weekdays):
        raise HTTPException(status_code=400, detail="Выберите хотя бы один день недели")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="Дата окончания раньше даты начала")
    if data.window_start == data.window_end:
        raise HTTPException(status_code=400, detail="Время начала и окончания совпадают")
    return weekdays


async def _assert_template(template_id: int, db: AsyncSession) -> None:
    tpl = (
        await db.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == template_id,
                ChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден или неактивен")


async def _assert_branches(branch_ids: list[int], current: Employee, db: AsyncSession) -> None:
    if not branch_ids:
        raise HTTPException(status_code=400, detail="Выберите филиал")
    allowed = await _allowed_branch_ids(current, db)
    if allowed is not None and any(b not in allowed for b in branch_ids):
        raise HTTPException(status_code=403, detail="Нет доступа к филиалу")


async def _to_out(rows: list[ChecklistSchedule], db: AsyncSession) -> list[ScheduleOut]:
    if not rows:
        return []
    tpl_names = {
        t.id: t.name
        for t in (
            await db.execute(
                select(ChecklistTemplate).where(ChecklistTemplate.id.in_({r.template_id for r in rows}))
            )
        ).scalars().all()
    }
    branch_names = {
        b.id: b.name
        for b in (
            await db.execute(select(Branch).where(Branch.id.in_({r.branch_id for r in rows})))
        ).scalars().all()
    }
    return [
        ScheduleOut(
            id=r.id,
            template_id=r.template_id,
            template_name=tpl_names.get(r.template_id, "—"),
            branch_id=r.branch_id,
            branch_name=branch_names.get(r.branch_id, "—"),
            shift=r.shift,
            start_date=r.start_date,
            end_date=r.end_date,
            weekdays=r.weekdays or [],
            window_start=r.window_start,
            window_end=r.window_end,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in rows
    ]


async def _get_or_404(schedule_id: int, current: Employee, db: AsyncSession) -> ChecklistSchedule:
    row = (
        await db.execute(select(ChecklistSchedule).where(ChecklistSchedule.id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    await _assert_branches([row.branch_id], current, db)
    return row


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    allowed = await _allowed_branch_ids(current, db)
    q = select(ChecklistSchedule).order_by(ChecklistSchedule.branch_id, ChecklistSchedule.window_start)
    if allowed is not None:
        q = q.where(ChecklistSchedule.branch_id.in_(allowed))
    rows = list((await db.execute(q)).scalars().all())
    return await _to_out(rows, db)


@router.post("", response_model=list[ScheduleOut])
async def create_schedules(
    data: ScheduleCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    weekdays = _validate(data)
    await _assert_template(data.template_id, db)
    await _assert_branches(data.branch_ids, current, db)

    rows: list[ChecklistSchedule] = []
    for branch_id in sorted(set(data.branch_ids)):
        row = ChecklistSchedule(
            template_id=data.template_id,
            branch_id=branch_id,
            shift=data.shift,
            start_date=data.start_date,
            end_date=data.end_date,
            weekdays=weekdays,
            window_start=data.window_start,
            window_end=data.window_end,
            is_active=True,
            created_by_employee_id=current.id,
        )
        db.add(row)
        rows.append(row)
    await db.flush()

    for row in rows:
        await log_action(
            db,
            actor_id=current.id,
            action="schedule.created",
            entity_type="checklist_schedule",
            entity_id=row.id,
            metadata={"template_id": row.template_id, "branch_id": row.branch_id},
        )
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return await _to_out(rows, db)


@router.put("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_404(schedule_id, current, db)
    weekdays = _validate(data)
    await _assert_template(data.template_id, db)
    await _assert_branches([data.branch_id], current, db)

    row.template_id = data.template_id
    row.branch_id = data.branch_id
    row.shift = data.shift
    row.start_date = data.start_date
    row.end_date = data.end_date
    row.weekdays = weekdays
    row.window_start = data.window_start
    row.window_end = data.window_end
    row.is_active = data.is_active

    await log_action(
        db,
        actor_id=current.id,
        action="schedule.updated",
        entity_type="checklist_schedule",
        entity_id=row.id,
        metadata={"is_active": row.is_active},
    )
    await db.commit()
    await db.refresh(row)
    return (await _to_out([row], db))[0]


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_404(schedule_id, current, db)
    await db.delete(row)
    await log_action(
        db,
        actor_id=current.id,
        action="schedule.deleted",
        entity_type="checklist_schedule",
        entity_id=schedule_id,
        metadata={},
    )
    await db.commit()
    return {"ok": True}
