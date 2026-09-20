import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.auth import get_current_user, get_current_web_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.models.user import User
from app.routers.audit_logs import log_action
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
_VALID_LANGS = frozenset({"ru", "uz", "en"})


def _gen_invite() -> str:
    return "".join(random.choices(INVITE_CHARS, k=8))


async def _get_own_role(current: Employee, db: AsyncSession) -> Role | None:
    return (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()


async def _assert_can_assign_role(role_id: int, current: Employee, db: AsyncSession) -> None:
    target_role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not target_role:
        raise HTTPException(status_code=404, detail="\u0420\u043e\u043b\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430")

    own_role = await _get_own_role(current, db)
    own_level = own_role.permission_level if own_role else 0
    if target_role.permission_level > own_level:
        raise HTTPException(
            status_code=403,
            detail="\u041d\u0435\u043b\u044c\u0437\u044f \u043d\u0430\u0437\u043d\u0430\u0447\u0438\u0442\u044c \u0440\u043e\u043b\u044c \u0441 \u0431\u043e\u043b\u0435\u0435 \u0432\u044b\u0441\u043e\u043a\u0438\u043c \u0443\u0440\u043e\u0432\u043d\u0435\u043c \u0434\u043e\u0441\u0442\u0443\u043f\u0430, \u0447\u0435\u043c \u0432\u0430\u0448 \u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439",
        )


async def _assert_branch_access_to_employee(emp: Employee, current: Employee, db: AsyncSession) -> None:
    """
    Raise 403 unless the acting manager has access to at least one of the
    target employee's branches.  Roles with can_access_all_branches=True
    are exempt and can act on any employee.
    """
    role = await _get_own_role(current, db)
    if role and role.can_access_all_branches:
        return
    own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
    existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
    if not (existing_branches & own_allowed_branches):
        raise HTTPException(status_code=403, detail="\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0443 \u0434\u0440\u0443\u0433\u043e\u0433\u043e \u0444\u0438\u043b\u0438\u0430\u043b\u0430")


# ── batch-aware builder ───────────────────────────────────────────────────────────────

def _employee_out_from_cache(
    emp: Employee,
    roles: dict[int, Role],
    branches: dict[int, Branch],
    claimed_employee_ids: set[int],
) -> EmployeeOut:
    role = roles.get(emp.role_id)
    branch = branches.get(emp.primary_branch_id)
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
        has_claimed_account=emp.id in claimed_employee_ids,
        telegram_linked=emp.telegram_id is not None,
        hired_at=emp.hired_at,
        preferred_language=emp.preferred_language or "ru",
        created_at=emp.created_at,
        updated_at=emp.updated_at,
    )


async def _build_employee_out(emp: Employee, db: AsyncSession) -> EmployeeOut:
    """Single-record builder \u2014 used after create/update (no list context)."""
    role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    branch = (await db.execute(select(Branch).where(Branch.id == emp.primary_branch_id))).scalar_one_or_none()
    account = (await db.execute(select(EmployeeAccount).where(EmployeeAccount.employee_id == emp.id))).scalar_one_or_none()
    roles = {emp.role_id: role} if role else {}
    branches = {emp.primary_branch_id: branch} if branch else {}
    claimed = {emp.id} if account else set()
    return _employee_out_from_cache(emp, roles, branches, claimed)


# ── endpoints ─────────────────────────────────────────────────────────────────────

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
        preferred_language=current.preferred_language or "ru",
    )


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    branch_id: int | None = None,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    role = (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()
    can_all = bool(role and role.can_access_all_branches)
    own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    if branch_id is not None and not can_all and branch_id not in own_allowed_branches:
        raise HTTPException(status_code=403, detail="\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0430\u043c \u0434\u0440\u0443\u0433\u043e\u0433\u043e \u0444\u0438\u043b\u0438\u0430\u043b\u0430")

    query = select(Employee)

    if branch_id is not None:
        query = query.where(
            or_(
                Employee.primary_branch_id == branch_id,
                Employee.additional_branch_ids.contains([branch_id]),
            )
        )
    elif not can_all:
        branch_list = list(own_allowed_branches)
        query = query.where(
            or_(
                Employee.primary_branch_id.in_(branch_list),
                *[Employee.additional_branch_ids.contains([bid]) for bid in branch_list],
            )
        )

    visible = (await db.execute(query)).scalars().all()

    if not visible:
        return []

    role_ids = {e.role_id for e in visible}
    branch_ids_set = {e.primary_branch_id for e in visible}
    emp_ids = {e.id for e in visible}

    roles_map: dict[int, Role] = {
        r.id: r
        for r in (await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
    }
    branches_map: dict[int, Branch] = {
        b.id: b
        for b in (await db.execute(select(Branch).where(Branch.id.in_(branch_ids_set)))).scalars().all()
    }
    claimed_ids: set[int] = {
        a.employee_id
        for a in (
            await db.execute(
                select(EmployeeAccount).where(EmployeeAccount.employee_id.in_(emp_ids))
            )
        ).scalars().all()
    }

    return [_employee_out_from_cache(e, roles_map, branches_map, claimed_ids) for e in visible]


@router.post("", response_model=EmployeeOut)
async def create_employee(
    data: EmployeeCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    await _assert_can_assign_role(data.role_id, current, db)

    role = await _get_own_role(current, db)
    can_all = bool(role and role.can_access_all_branches)
    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        target_branches = {data.primary_branch_id, *(data.additional_branch_ids or [])}
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="\u041d\u0435\u043b\u044c\u0437\u044f \u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0430 \u0432 \u0444\u0438\u043b\u0438\u0430\u043b, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u043c\u0443 \u0443 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430",
            )

    invite_code = _gen_invite()
    for _ in range(5):
        existing = (await db.execute(select(Employee).where(Employee.invite_code == invite_code))).scalar_one_or_none()
        if not existing:
            break
        invite_code = _gen_invite()

    lang = data.preferred_language if data.preferred_language in _VALID_LANGS else "ru"
    emp = Employee(
        full_name=data.full_name.strip(),
        phone=data.phone,
        role_id=data.role_id,
        primary_branch_id=data.primary_branch_id,
        additional_branch_ids=data.additional_branch_ids,
        status="active",
        invite_code=invite_code,
        hired_at=data.hired_at,
        preferred_language=lang,
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
        raise HTTPException(status_code=404, detail="\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")

    role = await _get_own_role(current, db)
    can_all = bool(role and role.can_access_all_branches)

    new_primary = data.primary_branch_id if data.primary_branch_id is not None else emp.primary_branch_id
    new_additional = data.additional_branch_ids if data.additional_branch_ids is not None else (emp.additional_branch_ids or [])

    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
        target_branches = {new_primary, *new_additional}
        if not (existing_branches & own_allowed_branches):
            raise HTTPException(status_code=403, detail="\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0443 \u0434\u0440\u0443\u0433\u043e\u0433\u043e \u0444\u0438\u043b\u0438\u0430\u043b\u0430")
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="\u041d\u0435\u043b\u044c\u0437\u044f \u043f\u0435\u0440\u0435\u0432\u0435\u0441\u0442\u0438 \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0430 \u0432 \u0444\u0438\u043b\u0438\u0430\u043b, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u043c\u0443 \u0443 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430",
            )

    if data.role_id is not None and data.role_id != emp.role_id:
        await _assert_can_assign_role(data.role_id, current, db)

    sent = data.model_fields_set
    if "full_name" in sent and data.full_name is not None:
        emp.full_name = data.full_name.strip()
    if "phone" in sent:
        emp.phone = data.phone
    if "role_id" in sent and data.role_id is not None:
        emp.role_id = data.role_id
    if "primary_branch_id" in sent and data.primary_branch_id is not None:
        emp.primary_branch_id = data.primary_branch_id
    if "additional_branch_ids" in sent and data.additional_branch_ids is not None:
        emp.additional_branch_ids = data.additional_branch_ids
    if "status" in sent and data.status is not None:
        emp.status = data.status
    if "hired_at" in sent:
        emp.hired_at = data.hired_at
    if "preferred_language" in sent and data.preferred_language is not None:
        if data.preferred_language in _VALID_LANGS:
            emp.preferred_language = data.preferred_language

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
        raise HTTPException(status_code=404, detail="\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")

    await _assert_branch_access_to_employee(emp, current, db)

    new_code = _gen_invite()
    emp.invite_code = new_code
    emp.telegram_id = None
    await db.commit()
    return {"invite_code": new_code}


@router.post("/claim", response_model=EmployeeOut)
async def claim_profile(
    body: ClaimRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    code = body.invite_code.strip().upper()
    target = (await db.execute(select(Employee).where(Employee.invite_code == code))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="\u041a\u043e\u0434 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
    if target.status != "active":
        raise HTTPException(status_code=403, detail="\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a \u0434\u0435\u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d")

    own_account = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.user_id == current_user.id)
    )).scalar_one_or_none()

    if own_account:
        if own_account.employee_id == target.id:
            return await _build_employee_out(target, db)
        raise HTTPException(status_code=409, detail="\u0412\u0430\u0448 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0443\u0436\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u0434\u0440\u0443\u0433\u043e\u043c\u0443 \u043f\u0440\u043e\u0444\u0438\u043b\u044e \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0430")

    already_claimed = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == target.id)
    )).scalar_one_or_none()
    if already_claimed:
        raise HTTPException(
            status_code=409,
            detail="\u042d\u0442\u043e\u0442 \u043f\u0440\u043e\u0444\u0438\u043b\u044c \u0443\u0436\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u0434\u0440\u0443\u0433\u043e\u043c\u0443 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0443. \u041f\u043e\u043f\u0440\u043e\u0441\u0438\u0442\u0435 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430 \u043e\u0442\u0432\u044f\u0437\u0430\u0442\u044c \u0435\u0433\u043e.",
        )

    account = EmployeeAccount(employee_id=target.id, user_id=current_user.id)
    db.add(account)
    await log_action(
        db, actor_id=target.id, action="employee.account_claimed", entity_type="employee", entity_id=target.id,
        metadata={"user_id": current_user.id},
    )
    await db.commit()
    return await _build_employee_out(target, db)


@router.delete("/{employee_id}/account")
async def unlink_employee_account(
    employee_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="\u0421\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")

    await _assert_branch_access_to_employee(emp, current, db)

    account = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id)
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u043d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d")

    await db.delete(account)
    await log_action(
        db, actor_id=current.id, action="employee.account_unlinked", entity_type="employee", entity_id=employee_id,
        metadata={"unlinked_user_id": account.user_id},
    )
    await db.commit()
    return {"ok": True}


@router.post("/bootstrap")
async def bootstrap_director(
    body: BootstrapRequest,
    db: AsyncSession = Depends(get_db),
):
    """\u0421\u043e\u0437\u0434\u0430\u0451\u0442 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0430 + \u0444\u0438\u043b\u0438\u0430\u043b (\u0442\u043e\u043b\u044c\u043a\u043e \u043f\u0440\u0438 \u043f\u0443\u0441\u0442\u043e\u0439 \u0411\u0414)."""
    count = (await db.execute(select(func.count()).select_from(Employee))).scalar_one()
    if count > 0:
        raise HTTPException(status_code=409, detail="\u0421\u0438\u0441\u0442\u0435\u043c\u0430 \u0443\u0436\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u0430")

    branch_name = body.branch_name.strip()
    if not branch_name:
        raise HTTPException(status_code=422, detail="\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0444\u0438\u043b\u0438\u0430\u043b\u0430 \u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u0431\u044b\u0442\u044c \u043f\u0443\u0441\u0442\u044b\u043c")

    director_role = (await db.execute(select(Role).where(Role.code == "director"))).scalar_one_or_none()
    if not director_role:
        director_role = Role(
            code="director",
            name_ru="\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440",
            category="management",
            permission_level=3,
            can_access_all_branches=True,
        )
        db.add(director_role)
        await db.flush()

    from app.models.branch import Branch as BranchModel
    branch = BranchModel(name=branch_name, timezone=body.timezone, is_active=True)
    db.add(branch)
    await db.flush()

    emp = Employee(
        full_name=body.full_name.strip(),
        role_id=director_role.id,
        status="active",
        invite_code=_gen_invite(),
        primary_branch_id=branch.id,
        additional_branch_ids=[],
        preferred_language="ru",
    )
    db.add(emp)
    await db.commit()
    return {"ok": True, "employee_id": emp.id, "branch_id": branch.id}
