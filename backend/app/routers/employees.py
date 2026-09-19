import random
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_user, require_manager, hash_password
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeOut,
    MyProfile,
    BootstrapRequest,
    ClaimRequest,
)

router = APIRouter(prefix="/employees", tags=["employees"])

INVITE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _gen_invite() -> str:
    return "".join(random.choices(INVITE_CHARS, k=8))


async def _get_own_role(current: Employee, db: AsyncSession) -> Role | None:
    return (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()


async def _assert_can_assign_role(role_id: int, current: Employee, db: AsyncSession) -> None:
    """
    Raise HTTP 403/404 unless `current` is allowed to grant `role_id` to someone
    (themselves included, via create/update employee).

    Rule: nobody can assign a role with a higher permission_level than their own.
    This blocks privilege escalation, e.g. a manager (level 1) granting a
    director role (level 3) to themselves or a colleague. A director (level 3)
    may still assign up to and including the director role.
    """
    target_role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not target_role:
        raise HTTPException(status_code=404, detail="Роль не найдена")

    own_role = await _get_own_role(current, db)
    own_level = own_role.permission_level if own_role else 0
    if target_role.permission_level > own_level:
        raise HTTPException(
            status_code=403,
            detail="Нельзя назначить роль с более высоким уровнем доступа, чем ваш собственный",
        )


async def _build_employee_out(emp: Employee, db: AsyncSession) -> EmployeeOut:
    role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    branch = (await db.execute(select(Branch).where(Branch.id == emp.primary_branch_id))).scalar_one_or_none()
    account = (await db.execute(select(EmployeeAccount).where(EmployeeAccount.employee_id == emp.id))).scalar_one_or_none()
    return EmployeeOut(
        id=emp.id,
        full_name=emp.full_name,
        phone=emp.phone,
        role_id=emp.role_id,
        role_name=role.name_ru if role else "\u2014",
        role_level=role.permission_level if role else 0,
        primary_branch_id=emp.primary_branch_id,
        primary_branch_name=branch.name if branch else "\u2014",
        additional_branch_ids=emp.additional_branch_ids or [],
        status=emp.status,
        invite_code=emp.invite_code,
        has_claimed_account=account is not None,
        telegram_linked=emp.telegram_id is not None,
        hired_at=emp.hired_at,
        created_at=emp.created_at,
        updated_at=emp.updated_at,
    )


@router.get("/any")
async def has_any_employees(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(Employee))
    count = result.scalar_one()
    return {"exists": count > 0}


@router.get("/me", response_model=MyProfile)
async def get_my_profile(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()
    branch = (await db.execute(select(Branch).where(Branch.id == current.primary_branch_id))).scalar_one_or_none()
    return MyProfile(
        id=current.id,
        full_name=current.full_name,
        status=current.status,
        role_id=current.role_id,
        role_name=role.name_ru if role else "\u2014",
        role_code=role.code if role else "",
        role_level=role.permission_level if role else 0,
        primary_branch_id=current.primary_branch_id,
        primary_branch_name=branch.name if branch else "\u2014",
        additional_branch_ids=current.additional_branch_ids or [],
    )


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    branch_id: int | None = None,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()
    can_all = bool(role and role.permission_level >= 2)

    own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    if branch_id is not None and not can_all and branch_id not in own_allowed_branches:
        # A manager who is not a supervisor/director cannot list employees of a
        # branch they don't belong to, even by passing branch_id explicitly.
        raise HTTPException(status_code=403, detail="Нет доступа к сотрудникам другого филиала")

    result = await db.execute(select(Employee))
    all_emps = result.scalars().all()

    visible = []
    for emp in all_emps:
        if branch_id is not None:
            if emp.primary_branch_id == branch_id or branch_id in (emp.additional_branch_ids or []):
                visible.append(emp)
        elif can_all:
            visible.append(emp)
        elif emp.primary_branch_id in own_allowed_branches or bool(
            own_allowed_branches & set(emp.additional_branch_ids or [])
        ):
            visible.append(emp)

    return [await _build_employee_out(e, db) for e in visible]


@router.post("", response_model=EmployeeOut)
async def create_employee(
    data: EmployeeCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    await _assert_can_assign_role(data.role_id, current, db)

    role = await _get_own_role(current, db)
    can_all = bool(role and role.permission_level >= 2)
    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        target_branches = {data.primary_branch_id, *(data.additional_branch_ids or [])}
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="Нельзя добавить сотрудника в филиал, к которому у вас нет доступа",
            )

    invite_code = _gen_invite()
    for _ in range(5):
        existing = (await db.execute(select(Employee).where(Employee.invite_code == invite_code))).scalar_one_or_none()
        if not existing:
            break
        invite_code = _gen_invite()

    emp = Employee(
        full_name=data.full_name.strip(),
        phone=data.phone,
        role_id=data.role_id,
        primary_branch_id=data.primary_branch_id,
        additional_branch_ids=data.additional_branch_ids,
        status="active",
        invite_code=invite_code,
        hired_at=data.hired_at,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return await _build_employee_out(emp, db)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    role = await _get_own_role(current, db)
    can_all = bool(role and role.permission_level >= 2)
    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
        target_branches = {data.primary_branch_id, *(data.additional_branch_ids or [])}
        # Must already have access to this employee's current branch(es), and
        # must not move them into a branch outside the caller's own access.
        if not (existing_branches & own_allowed_branches):
            raise HTTPException(status_code=403, detail="Нет доступа к сотруднику другого филиала")
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="Нельзя перевести сотрудника в филиал, к которому у вас нет доступа",
            )

    if data.role_id != emp.role_id:
        # Changing someone's role is where privilege escalation would happen:
        # never let a caller grant a role above their own permission level.
        await _assert_can_assign_role(data.role_id, current, db)

    emp.full_name = data.full_name.strip()
    emp.phone = data.phone
    emp.role_id = data.role_id
    emp.primary_branch_id = data.primary_branch_id
    emp.additional_branch_ids = data.additional_branch_ids
    emp.status = data.status
    if data.hired_at is not None:
        emp.hired_at = data.hired_at

    await db.commit()
    await db.refresh(emp)
    return await _build_employee_out(emp, db)


@router.post("/{employee_id}/regenerate-invite")
async def regenerate_invite(
    employee_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    role = await _get_own_role(current, db)
    can_all = bool(role and role.permission_level >= 2)
    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
        if not (existing_branches & own_allowed_branches):
            raise HTTPException(status_code=403, detail="Нет доступа к сотруднику другого филиала")

    new_code = _gen_invite()
    emp.invite_code = new_code
    # A fresh code invalidates any previous Telegram link, so the new code can be
    # claimed again (e.g. employee lost their phone / lost access to the old chat).
    emp.telegram_id = None
    await db.commit()
    return {"invite_code": new_code}


@router.post("/claim")
async def claim_profile(
    body: ClaimRequest,
    current_user_employee: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == current_user_employee.id)
    )).scalar_one_or_none()
    if account:
        raise HTTPException(status_code=409, detail="Профиль уже привязан")

    code = body.invite_code.strip().upper()
    target = (await db.execute(select(Employee).where(Employee.invite_code == code))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Код приглашения не найден")
    if target.status != "active":
        raise HTTPException(status_code=403, detail="Сотрудник деактивирован")

    already = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == target.id)
    )).scalar_one_or_none()
    if already:
        raise HTTPException(status_code=409, detail="Этот профиль уже привязан к другому аккаунту")

    return {"ok": True}


@router.post("/bootstrap")
async def bootstrap_director(
    body: BootstrapRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создаёт первого директора + филиал (только при пустой БД)."""
    count = (await db.execute(select(func.count()).select_from(Employee))).scalar_one()
    if count > 0:
        raise HTTPException(status_code=409, detail="Система уже настроена")

    director_role = (await db.execute(select(Role).where(Role.code == "director"))).scalar_one_or_none()
    if not director_role:
        director_role = Role(code="director", name_ru="Директор", category="management", permission_level=3)
        db.add(director_role)
        await db.flush()

    branch = Branch(name=body.branch_name.strip() or "Главный филиал", timezone=body.timezone, is_active=True)
    db.add(branch)
    await db.flush()

    emp = Employee(
        full_name=body.full_name.strip(),
        role_id=director_role.id,
        status="active",
        invite_code=_gen_invite(),
        primary_branch_id=branch.id,
        additional_branch_ids=[],
    )
    db.add(emp)
    await db.commit()
    return {"ok": True, "employee_id": emp.id, "branch_id": branch.id}
