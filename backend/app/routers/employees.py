import random
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user, get_current_web_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.models.user import User
from app.routers.audit_logs import log_action
from app.telegram import notify_employee_approved, notify_employee_rejected
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeApprove,
    EmployeeOut,
    MyProfile,
    BootstrapRequest,
    ClaimRequest,
)

# NOTE: DELETE /employees/{id} lives in app/routers/employee_removal.py

router = APIRouter(prefix="/employees", tags=["employees"])

INVITE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_VALID_LANGS = frozenset({"ru", "uz", "en"})
_MAX_INVITE_ATTEMPTS = 10

_VALID_STATUSES = frozenset({"pending", "active", "blocked", "archived", "inactive", "fired"})

logger = logging.getLogger(__name__)


def _gen_invite() -> str:
    return "".join(random.choices(INVITE_CHARS, k=8))


async def _get_own_role(current: Employee, db: AsyncSession) -> Role | None:
    if current.role_id is None:
        return None
    return (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()


async def _assert_can_assign_role(role_id: int, current: Employee, db: AsyncSession) -> None:
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


async def _assert_branch_access_to_employee(emp: Employee, current: Employee, db: AsyncSession) -> None:
    if emp.primary_branch_id is None:
        return
    role = await _get_own_role(current, db)
    if role and role.can_access_all_branches:
        return
    own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
    existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
    if not (existing_branches & own_allowed_branches):
        raise HTTPException(status_code=403, detail="Нет доступа к сотруднику другого филиала")


# ── batch-aware builder ────────────────────────────────────────────────────────────────

def _employee_out_from_cache(
    emp: Employee,
    roles: dict[int, Role],
    branches: dict[int, Branch],
    claimed_employee_ids: set[int],
) -> EmployeeOut:
    role = roles.get(emp.role_id) if emp.role_id is not None else None
    branch = branches.get(emp.primary_branch_id) if emp.primary_branch_id is not None else None
    return EmployeeOut(
        id=emp.id,
        full_name=emp.full_name,
        phone=emp.phone,
        role_id=emp.role_id,
        role_name=role.name_ru if role else (None if emp.role_id is None else "—"),
        role_level=role.permission_level if role else 0,
        primary_branch_id=emp.primary_branch_id,
        primary_branch_name=branch.name if branch else (None if emp.primary_branch_id is None else "—"),
        additional_branch_ids=emp.additional_branch_ids or [],
        status=emp.status,
        invite_code=emp.invite_code,
        has_claimed_account=emp.id in claimed_employee_ids,
        telegram_linked=emp.telegram_id is not None,
        telegram_id=emp.telegram_id,
        telegram_username=emp.telegram_username,
        hired_at=emp.hired_at,
        preferred_language=emp.preferred_language or "ru",
        last_activity_at=emp.last_activity_at.isoformat() if emp.last_activity_at else None,
        created_at=emp.created_at,
        updated_at=emp.updated_at,
    )


async def _build_employee_out(emp: Employee, db: AsyncSession) -> EmployeeOut:
    role = None
    if emp.role_id is not None:
        role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    branch = None
    if emp.primary_branch_id is not None:
        branch = (await db.execute(select(Branch).where(Branch.id == emp.primary_branch_id))).scalar_one_or_none()
    account = (await db.execute(select(EmployeeAccount).where(EmployeeAccount.employee_id == emp.id))).scalar_one_or_none()
    roles = {emp.role_id: role} if role else {}
    branches = {emp.primary_branch_id: branch} if branch else {}
    claimed = {emp.id} if account else set()
    return _employee_out_from_cache(emp, roles, branches, claimed)


# ── invite-code helper ────────────────────────────────────────────────────────────────────

async def _insert_employee_with_unique_invite(
    emp: Employee,
    db: AsyncSession,
) -> None:
    for attempt in range(_MAX_INVITE_ATTEMPTS):
        try:
            db.add(emp)
            await db.flush()
            return
        except IntegrityError as exc:
            await db.rollback()
            err = str(exc.orig).lower()
            if "uq_employees_invite_code" not in err and "invite_code" not in err:
                raise
            emp.invite_code = _gen_invite()
            logger.warning(
                "invite_code collision on attempt %d/%d, retrying with %s",
                attempt + 1, _MAX_INVITE_ATTEMPTS, emp.invite_code,
            )

    raise HTTPException(
        status_code=500,
        detail="Не удалось сгенерировать уникальный invite-код. Попробуйте ещё раз.",
    )


# ── endpoints ──────────────────────────────────────────────────────────────────────────────

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
        role_name=role.name_ru if role else "—",
        role_code=role.code if role else "",
        role_level=role.permission_level if role else 0,
        primary_branch_id=current.primary_branch_id,
        primary_branch_name=branch.name if branch else "—",
        additional_branch_ids=current.additional_branch_ids or [],
        preferred_language=current.preferred_language or "ru",
    )


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    branch_id: int | None = None,
    q: str | None = None,
    status: str | None = None,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Неверный статус")

    role = await _get_own_role(current, db)
    can_all = bool(role and role.can_access_all_branches)
    own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    if branch_id is not None and not can_all and branch_id not in own_allowed_branches:
        raise HTTPException(status_code=403, detail="Нет доступа к сотрудникам другого филиала")

    query = select(Employee)

    if branch_id is not None:
        query = query.where(
            or_(
                Employee.primary_branch_id == branch_id,
                Employee.additional_branch_ids.contains([branch_id]),
                Employee.status == "pending",
            )
        )
    elif not can_all:
        branch_list = list(own_allowed_branches)
        query = query.where(
            or_(
                Employee.primary_branch_id.in_(branch_list),
                *[Employee.additional_branch_ids.contains([bid]) for bid in branch_list],
                Employee.status == "pending",
            )
        )

    if status is not None:
        query = query.where(Employee.status == status)

    if q:
        term = q.strip()
        if term:
            conditions = [Employee.full_name.ilike(f"%{term}%")]
            if Employee.phone is not None:
                conditions.append(Employee.phone.ilike(f"%{term}%"))
            if term.isdigit():
                conditions.append(Employee.telegram_id == int(term))
            query = query.where(or_(*conditions))

    visible = (await db.execute(query.order_by(Employee.created_at.desc()))).scalars().all()

    if not visible:
        return []

    role_ids = {e.role_id for e in visible if e.role_id is not None}
    branch_ids_set = {e.primary_branch_id for e in visible if e.primary_branch_id is not None}
    emp_ids = {e.id for e in visible}

    roles_map: dict[int, Role] = {
        r.id: r
        for r in (await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
    } if role_ids else {}
    branches_map: dict[int, Branch] = {
        b.id: b
        for b in (await db.execute(select(Branch).where(Branch.id.in_(branch_ids_set)))).scalars().all()
    } if branch_ids_set else {}
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
                detail="Нельзя добавить сотрудника в филиал, к которому у вас нет доступа",
            )

    lang = data.preferred_language if data.preferred_language in _VALID_LANGS else "ru"
    emp = Employee(
        full_name=data.full_name.strip(),
        phone=data.phone,
        role_id=data.role_id,
        primary_branch_id=data.primary_branch_id,
        additional_branch_ids=data.additional_branch_ids,
        status="active",
        invite_code=_gen_invite(),
        hired_at=data.hired_at,
        preferred_language=lang,
    )
    await _insert_employee_with_unique_invite(emp, db)
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
    can_all = bool(role and role.can_access_all_branches)

    new_primary = data.primary_branch_id if data.primary_branch_id is not None else emp.primary_branch_id
    new_additional = data.additional_branch_ids if data.additional_branch_ids is not None else (emp.additional_branch_ids or [])

    if not can_all and emp.primary_branch_id is not None:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        existing_branches = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
        target_branches = {b for b in {new_primary, *new_additional} if b is not None}
        if not (existing_branches & own_allowed_branches):
            raise HTTPException(status_code=403, detail="Нет доступа к сотруднику другого филиала")
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="Нельзя перевести сотрудника в филиал, к которому у вас нет доступа",
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
        if data.status not in _VALID_STATUSES:
            raise HTTPException(status_code=422, detail="Неверный статус")
        # Note: keep telegram_id linked when status leaves "active". Clearing
        # it here would let a blocked/archived employee re-register as a new
        # "pending" profile via the bot's self-service flow, bypassing the
        # block. /bot/resync already returns 403 for a non-active employee,
        # and the bot handles that 403 by showing a status message instead
        # of a raw error.
        emp.status = data.status
    if "hired_at" in sent:
        emp.hired_at = data.hired_at
    if "preferred_language" in sent and data.preferred_language is not None:
        if data.preferred_language in _VALID_LANGS:
            emp.preferred_language = data.preferred_language

    await db.commit()
    await db.refresh(emp)
    return await _build_employee_out(emp, db)


@router.post("/{employee_id}/approve", response_model=EmployeeOut)
async def approve_employee(
    employee_id: int,
    data: EmployeeApprove,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    await _assert_can_assign_role(data.role_id, current, db)

    role = await _get_own_role(current, db)
    can_all = bool(role and role.can_access_all_branches)
    if not can_all:
        own_allowed_branches = {current.primary_branch_id, *(current.additional_branch_ids or [])}
        target_branches = {data.primary_branch_id, *(data.additional_branch_ids or [])}
        if not target_branches <= own_allowed_branches:
            raise HTTPException(
                status_code=403,
                detail="Нельзя назначить сотрудника в филиал, к которому у вас нет доступа",
            )

    assigned_role = (await db.execute(select(Role).where(Role.id == data.role_id))).scalar_one_or_none()
    assigned_branch = (await db.execute(select(Branch).where(Branch.id == data.primary_branch_id))).scalar_one_or_none()
    lang = emp.preferred_language or "ru"
    role_name = assigned_role.name_ru if assigned_role else "—"
    branch_name = assigned_branch.name if assigned_branch else "—"
    tg_id = emp.telegram_id

    emp.role_id = data.role_id
    emp.primary_branch_id = data.primary_branch_id
    emp.additional_branch_ids = data.additional_branch_ids
    emp.status = "active"
    if data.hired_at:
        emp.hired_at = data.hired_at
    if not emp.invite_code:
        emp.invite_code = _gen_invite()

    await log_action(
        db, actor_id=current.id, action="employee.approved", entity_type="employee", entity_id=emp.id,
        metadata={"role_id": data.role_id, "primary_branch_id": data.primary_branch_id},
    )
    await db.commit()
    await db.refresh(emp)

    await notify_employee_approved(tg_id, lang, role_name, branch_name)

    return await _build_employee_out(emp, db)


@router.post("/{employee_id}/reject")
async def reject_employee(
    employee_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if emp.status != "pending":
        raise HTTPException(status_code=400, detail="Можно отклонить только заявки на рассмотрении")

    tg_id = emp.telegram_id
    lang = emp.preferred_language or "ru"

    await log_action(
        db, actor_id=current.id, action="employee.rejected", entity_type="employee", entity_id=emp.id,
        metadata={"full_name": emp.full_name, "telegram_id": emp.telegram_id},
    )
    await db.delete(emp)
    await db.commit()

    await notify_employee_rejected(tg_id, lang)

    return {"ok": True}


@router.post("/{employee_id}/regenerate-invite")
async def regenerate_invite(
    employee_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    emp = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    await _assert_branch_access_to_employee(emp, current, db)

    for attempt in range(_MAX_INVITE_ATTEMPTS):
        new_code = _gen_invite()
        emp.invite_code = new_code
        emp.telegram_id = None
        emp.bot_session_token_hash = None
        try:
            await db.flush()
            break
        except IntegrityError as exc:
            await db.rollback()
            err = str(exc.orig).lower()
            if "uq_employees_invite_code" not in err and "invite_code" not in err:
                raise
            logger.warning(
                "regenerate_invite: collision on attempt %d/%d for employee %d",
                attempt + 1, _MAX_INVITE_ATTEMPTS, employee_id,
            )
    else:
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать уникальный invite-код.")

    await db.commit()
    return {"invite_code": emp.invite_code}


@router.post("/claim", response_model=EmployeeOut)
async def claim_profile(
    body: ClaimRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    code = body.invite_code.strip().upper()
    target = (await db.execute(select(Employee).where(Employee.invite_code == code))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Код приглашения не найден")
    if target.status != "active":
        raise HTTPException(status_code=403, detail="Сотрудник деактивирован")

    own_account = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.user_id == current_user.id)
    )).scalar_one_or_none()

    if own_account:
        if own_account.employee_id == target.id:
            return await _build_employee_out(target, db)
        raise HTTPException(status_code=409, detail="Ваш аккаунт уже привязан к другому профилю сотрудника")

    already_claimed = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == target.id)
    )).scalar_one_or_none()
    if already_claimed:
        raise HTTPException(
            status_code=409,
            detail="Этот профиль уже привязан к другому аккаунту. Попросите менеджера отвязать его.",
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
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    await _assert_branch_access_to_employee(emp, current, db)

    account = (await db.execute(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id)
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не привязан")

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
    """Создаёт первого директора + филиал (только при пустой БД)."""
    count = (await db.execute(select(func.count()).select_from(Employee))).scalar_one()
    if count > 0:
        raise HTTPException(status_code=409, detail="Система уже настроена")

    branch_name = body.branch_name.strip()
    if not branch_name:
        raise HTTPException(status_code=422, detail="Название филиала не может быть пустым")

    director_role = (await db.execute(select(Role).where(Role.code == "director"))).scalar_one_or_none()
    if not director_role:
        director_role = Role(
            code="director",
            name_ru="Директор",
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
    await _insert_employee_with_unique_invite(emp, db)
    await db.commit()
    return {"ok": True, "employee_id": emp.id, "branch_id": branch.id}
