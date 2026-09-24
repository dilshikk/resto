"""
DELETE /employees/{id} — remove an employee from the web panel.

Goal: after deletion the person's Telegram account is "unknown" again, so the
next message to the bot starts a brand-new self-registration (GET /bot/status
returns "not_registered").

Two outcomes:
  * "deleted"  — the employee had no history, the row is removed entirely.
  * "archived" — the employee is referenced by history (checklists, photos,
                 issues, audit logs...). Removing the row would break those
                 reports, so it is kept with status="archived" but fully
                 detached from Telegram and the web account.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_manager
from app.database import get_db
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.routers.audit_logs import log_action
from app.routers.employees import _assert_branch_access_to_employee

router = APIRouter(prefix="/employees", tags=["employees"])


async def _role_level(role_id: int | None, db: AsyncSession) -> int:
    if role_id is None:
        return 0
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    return role.permission_level if role else 0


async def _load_employee(employee_id: int, db: AsyncSession) -> Employee | None:
    # populate_existing: reload fresh state after a rolled-back savepoint
    # (expired attributes cannot be lazy-loaded in async SQLAlchemy).
    return (
        await db.execute(
            select(Employee)
            .where(Employee.id == employee_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = await _load_employee(employee_id, db)
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if emp.id == current.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")

    await _assert_branch_access_to_employee(emp, current, db)

    if await _role_level(emp.role_id, db) > await _role_level(current.role_id, db):
        raise HTTPException(
            status_code=403,
            detail="Нельзя удалить сотрудника с более высоким уровнем доступа",
        )

    metadata = {"full_name": emp.full_name, "telegram_id": emp.telegram_id}

    try:
        async with db.begin_nested():
            await db.execute(delete(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id))
            await db.delete(emp)
            await db.flush()
        mode = "deleted"
    except IntegrityError:
        # Referenced by history rows — keep the row, but detach everything that
        # identifies the person so the bot treats them as a new user.
        emp = await _load_employee(employee_id, db)
        if not emp:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        await db.execute(delete(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id))
        emp.telegram_id = None
        emp.telegram_username = None
        emp.bot_session_token_hash = None
        emp.invite_code = None
        emp.status = "archived"
        mode = "archived"

    await log_action(
        db,
        actor_id=current.id,
        action="employee.deleted" if mode == "deleted" else "employee.archived_and_detached",
        entity_type="employee",
        entity_id=employee_id,
        metadata=metadata,
    )
    await db.commit()
    return {"ok": True, "mode": mode}
