from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.shift import Shift
from app.schemas.shift import ShiftCreate, ShiftUpdate, ShiftOut

router = APIRouter(prefix="/shifts", tags=["shifts"])

VALID_STATUSES = {"planned", "active", "completed", "no_show"}


async def _build_out(shift: Shift, db: AsyncSession) -> ShiftOut:
    emp = (await db.execute(select(Employee).where(Employee.id == shift.employee_id))).scalar_one_or_none()
    branch = (await db.execute(select(Branch).where(Branch.id == shift.branch_id))).scalar_one_or_none()
    return ShiftOut(
        id=shift.id,
        employee_id=shift.employee_id,
        employee_name=emp.full_name if emp else "—",
        branch_id=shift.branch_id,
        branch_name=branch.name if branch else "—",
        shift_date=shift.shift_date,
        starts_at=shift.starts_at,
        ends_at=shift.ends_at,
        status=shift.status,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
    )


@router.get("", response_model=list[ShiftOut])
async def list_shifts(
    branch_id: int | None = None,
    employee_id: int | None = None,
    shift_date: str | None = None,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список смен. Сотрудник без прав менеджера видит только свои смены."""
    q = select(Shift)
    if branch_id:
        q = q.where(Shift.branch_id == branch_id)
    if shift_date:
        q = q.where(Shift.shift_date == shift_date)
    if employee_id:
        q = q.where(Shift.employee_id == employee_id)

    shifts = (await db.execute(q.order_by(Shift.shift_date.desc()))).scalars().all()
    return [await _build_out(s, db) for s in shifts]


@router.get("/my-current", response_model=ShiftOut | None)
async def my_current_shift(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Текущая активная или ближайшая запланированная смена сотрудника."""
    q = (
        select(Shift)
        .where(Shift.employee_id == current.id, Shift.status.in_(["planned", "active"]))
        .order_by(Shift.shift_date.asc())
    )
    shift = (await db.execute(q)).scalars().first()
    return await _build_out(shift, db) if shift else None


@router.post("", response_model=ShiftOut)
async def create_shift(
    data: ShiftCreate,
    _: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    shift = Shift(
        employee_id=data.employee_id,
        branch_id=data.branch_id,
        shift_date=data.shift_date,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        status="planned",
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return await _build_out(shift, db)


@router.patch("/{shift_id}", response_model=ShiftOut)
async def update_shift(
    shift_id: int,
    data: ShiftUpdate,
    _: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    shift = (await db.execute(select(Shift).where(Shift.id == shift_id))).scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Смена не найдена")

    if data.status is not None:
        if data.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Статус должен быть одним из: {', '.join(VALID_STATUSES)}")
        shift.status = data.status
    if data.starts_at is not None:
        shift.starts_at = data.starts_at
    if data.ends_at is not None:
        shift.ends_at = data.ends_at

    await db.commit()
    await db.refresh(shift)
    return await _build_out(shift, db)
