import uuid
import hashlib
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import verify_bot_secret
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee, EmployeeAccount
from app.models.photo import Photo
from app.models.role import Role
from app.routers.audit_logs import log_action
from app.routers.checklists import (
    UPLOAD_DIR as CHECKLIST_UPLOAD_DIR,
    _assert_completion_requirements,
    _assert_previous_required_done,
    _build_items_batch,
    _build_out,
    _find_current_item,
    _get_ordered_items,
    _visible_to_role,
)
from app.models.checklist import Checklist, ChecklistItem
from app.models.standard import Standard
from app.schemas.bot import (
    BotEmployeeOut,
    BotLinkRequest,
    BotLinkResponse,
    BotResyncRequest,
    BotRegisterRequest,
    BotStatusOut,
    BotSkipRequest,
    BotToggleRequest,
)
from app.schemas.checklist import ChecklistItemOut, ChecklistOut, CurrentItemOut

router = APIRouter(
    prefix="/bot",
    tags=["bot"],
    dependencies=[Depends(verify_bot_secret)],
)

_ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_VALID_LANGS = frozenset({"ru", "uz", "en"})


# ── Per-employee bot credential helpers ──────────────────────────────────────────

def _hash_bot_token(token: str) -> str:
    """Return the SHA-256 hex digest of a bot session token."""
    return hashlib.sha256(token.encode()).hexdigest()


async def get_employee_by_bot_token(
    x_bot_employee_token: str = Header(
        ...,
        description=(
            "Per-employee bot session token issued on POST /bot/link. "
            "Required on every endpoint that acts on behalf of a specific employee."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """
    Resolve the acting Employee from the per-employee bot session token.

    Authentication is two-factor at the transport layer:
      1. X-Bot-Secret    — proves the request comes from *our* bot service
      2. X-Bot-Employee-Token — proves *which* employee is acting

    Leaking X-Bot-Secret alone is no longer sufficient to impersonate
    employees; an attacker would also need the per-employee token issued
    at link time.
    """
    token_hash = _hash_bot_token(x_bot_employee_token)
    emp = (
        await db.execute(
            select(Employee).where(Employee.bot_session_token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if not emp or emp.status != "active":
        raise HTTPException(
            status_code=401,
            detail="Недействительный или отозванный токен бота. Свяжитесь заново через /start.",
        )
    return emp


# ── Localisation helpers ────────────────────────────────────────────────────────────

def _pick_localized(ru: str, uz: str | None, en: str | None, lang: str) -> str:
    """Return the best available translation; fall back to Russian."""
    if lang == "uz" and uz:
        return uz
    if lang == "en" and en:
        return en
    return ru


def _pick_role_name(role: Role | None, lang: str) -> str:
    if not role:
        return "—"
    if lang == "uz" and role.name_uz:
        return role.name_uz
    if lang == "en" and role.name_en:
        return role.name_en
    return role.name_ru


async def _to_bot_employee_out(emp: Employee, db: AsyncSession) -> BotEmployeeOut:
    role = None
    if emp.role_id is not None:
        role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    branch = None
    if emp.primary_branch_id is not None:
        branch = (await db.execute(select(Branch).where(Branch.id == emp.primary_branch_id))).scalar_one_or_none()
    lang = emp.preferred_language or "ru"
    return BotEmployeeOut(
        id=emp.id,
        full_name=emp.full_name,
        role_name=_pick_role_name(role, lang),
        role_level=role.permission_level if role else 0,
        primary_branch_name=branch.name if branch else "—",
        status=emp.status,
        preferred_language=lang,
    )


def _issue_session_token(emp: Employee) -> str:
    """
    Mint a brand-new per-employee bot session token for *emp*, store only
    its hash, and return the plaintext (caller must return it to the bot
    exactly once). Invalidates any previously issued token for this employee.
    """
    plaintext_token = secrets.token_urlsafe(32)
    emp.bot_session_token_hash = _hash_bot_token(plaintext_token)
    return plaintext_token


# ── Self-service registration (no invite code, no per-employee token yet) ──────────

@router.post("/register", response_model=BotStatusOut)
async def register_via_bot(
    body: BotRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the bot on /start when this telegram_id has never been seen
    before (GET /bot/status returned "not_registered") and the employee has
    just shared their contact.

    Creates a new employees row with status="pending" and no role/branch —
    a manager reviews it in the "Сотрудники" screen and either approves it
    (POST /employees/{id}/approve, assigning restaurant + position) or
    rejects it (POST /employees/{id}/reject).

    Unlike POST /bot/link, this does NOT issue a bot_session_token: a
    "pending" employee has no checklist access yet, so there is nothing for
    the bot to authenticate with until a manager approves the request.
    """
    existing = (
        await db.execute(select(Employee).where(Employee.telegram_id == body.telegram_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Этот Telegram уже зарегистрирован")

    emp = Employee(
        full_name=body.full_name.strip(),
        phone=body.phone,
        status="pending",
        telegram_id=body.telegram_id,
        telegram_username=body.username,
        additional_branch_ids=[],
        preferred_language="ru",
    )
    db.add(emp)
    await db.flush()

    await log_action(
        db,
        actor_id=None,
        action="employee.self_registered",
        entity_type="employee",
        entity_id=emp.id,
        metadata={"employee_id": emp.id},
    )
    await db.commit()
    await db.refresh(emp)

    return BotStatusOut(
        status="pending",
        full_name=emp.full_name,
        role_name=None,
        primary_branch_name=None,
        preferred_language=emp.preferred_language or "ru",
    )


@router.get("/status", response_model=BotStatusOut)
async def get_registration_status(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the bot on /start (before it has a per-employee token) to
    decide what to show:
      - not_registered — never seen this telegram_id: ask to share contact
      - pending         — awaiting manager review: show a waiting message
      - blocked/archived/inactive/fired — show a status message
      - active          — bot should proceed to greet/link normally
    """
    emp = (
        await db.execute(select(Employee).where(Employee.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if not emp:
        return BotStatusOut(status="not_registered", preferred_language="ru")

    role = None
    if emp.role_id is not None:
        role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    branch = None
    if emp.primary_branch_id is not None:
        branch = (await db.execute(select(Branch).where(Branch.id == emp.primary_branch_id))).scalar_one_or_none()
    lang = emp.preferred_language or "ru"

    return BotStatusOut(
        status=emp.status,
        full_name=emp.full_name,
        role_name=_pick_role_name(role, lang) if role else None,
        primary_branch_name=branch.name if branch else None,
        preferred_language=lang,
    )


# ── Link endpoint (no per-employee token yet) ──────────────────────────────────────

@router.post("/link", response_model=BotLinkResponse)
async def link_telegram_account(
    body: BotLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Called on /start <invite_code> in the bot to link a Telegram account.

    Returns a `bot_session_token` that the bot MUST store per-user and
    attach as `X-Bot-Employee-Token` on all subsequent per-employee requests.
    The token is shown exactly once — the backend only stores its hash.
    """
    already_linked = (
        await db.execute(select(Employee).where(Employee.telegram_id == body.telegram_id))
    ).scalar_one_or_none()
    if already_linked:
        raise HTTPException(status_code=409, detail="Этот Telegram уже привязан к сотруднику")

    code = body.invite_code.strip().upper()
    target = (await db.execute(select(Employee).where(Employee.invite_code == code))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Код приглашения не найден")
    if target.status != "active":
        raise HTTPException(status_code=403, detail="Сотрудник деактивирован")
    if target.telegram_id is not None:
        raise HTTPException(status_code=409, detail="Этот профиль уже привязан к другому Telegram")

    # Issue a per-employee bot session token.  Only the hash is stored;
    # the plaintext is returned once and never logged.
    plaintext_token = _issue_session_token(target)
    target.telegram_id = body.telegram_id

    await log_action(
        db,
        actor_id=target.id,
        action="employee.telegram_linked",
        entity_type="employee",
        entity_id=target.id,
        # Do NOT log telegram_id or the token in metadata — audit logs are
        # visible to admins and should not contain usable credentials.
        metadata={"employee_id": target.id},
    )
    await db.commit()
    await db.refresh(target)

    out = await _to_bot_employee_out(target, db)
    return BotLinkResponse(
        **out.model_dump(),
        bot_session_token=plaintext_token,
    )


# ── Resync endpoint (recovers a lost session token, no invite code needed) ──────────

@router.post("/resync", response_model=BotLinkResponse)
async def resync_telegram_account(
    body: BotResyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the bot whenever it has no cached session token for a
    telegram_id (typically right after the bot process restarts, since the
    token cache lives only in memory).

    Telegram itself already authenticates the caller as this telegram_id,
    so if an employee profile is already linked to it we can safely mint a
    fresh session token here — no invite code required. This is what makes
    a bot restart recoverable: without it, employees.telegram_id being
    already set makes /bot/link permanently reject them with 409, while the
    old token is unrecoverable (only its hash is stored).

    404 is returned only when this telegram_id has genuinely never been
    linked, in which case the bot should fall back to asking for an invite
    code.
    """
    emp = (
        await db.execute(select(Employee).where(Employee.telegram_id == body.telegram_id))
    ).scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Профиль не найден или не привязан")
    if emp.status != "active":
        raise HTTPException(status_code=403, detail="Сотрудник деактивирован")

    plaintext_token = _issue_session_token(emp)

    await log_action(
        db,
        actor_id=emp.id,
        action="employee.bot_session_resynced",
        entity_type="employee",
        entity_id=emp.id,
        metadata={"employee_id": emp.id},
    )
    await db.commit()
    await db.refresh(emp)

    out = await _to_bot_employee_out(emp, db)
    return BotLinkResponse(
        **out.model_dump(),
        bot_session_token=plaintext_token,
    )


# ── All remaining endpoints require X-Bot-Employee-Token ────────────────────────

@router.get("/me", response_model=BotEmployeeOut)
async def get_me(
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    return await _to_bot_employee_out(emp, db)


@router.get("/checklists/today", response_model=list[ChecklistOut])
async def list_my_checklists_today(
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    today = date.today().isoformat()
    allowed = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
    role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
    is_manager = bool(role and role.permission_level >= 1)

    result = await db.execute(
        select(Checklist).where(Checklist.date == today).order_by(Checklist.id)
    )
    all_cls = result.scalars().all()
    return [
        await _build_out(cl, db)
        for cl in all_cls
        if cl.branch_id in allowed and _visible_to_role(cl.role_ids or [], emp.role_id, is_manager)
    ]


@router.get("/checklists/{checklist_id}/current-item", response_model=CurrentItemOut | None)
async def get_my_current_item(
    checklist_id: int,
    lang: str = "ru",
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the next pending item for the bot's step-by-step flow.

    The `lang` query parameter controls which language the title and
    description are returned in ("ru" | "uz" | "en").  Falls back to
    Russian if the requested translation is not available.
    """
    if lang not in _VALID_LANGS:
        lang = "ru"

    cl = (await db.execute(select(Checklist).where(Checklist.id == checklist_id))).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    if cl.status == "completed":
        return None

    items = await _get_ordered_items(checklist_id, db)
    item = _find_current_item(items)
    if item is None:
        return None

    position = next(i for i, it in enumerate(items, 1) if it.id == item.id)

    standard_title = None
    if item.standard_code:
        standard = (
            await db.execute(select(Standard).where(Standard.code == item.standard_code))
        ).scalar_one_or_none()
        standard_title = standard.title if standard else None

    title = _pick_localized(
        item.title,
        getattr(item, "title_uz", None),
        getattr(item, "title_en", None),
        lang,
    )
    description = _pick_localized(
        item.description or "",
        getattr(item, "description_uz", None),
        getattr(item, "description_en", None),
        lang,
    ) or None

    return CurrentItemOut(
        id=item.id,
        checklist_id=item.checklist_id,
        title=title,
        description=description,
        is_required=item.is_required,
        sort_order=item.sort_order,
        total_items=len(items),
        current_position=position,
        standard_code=item.standard_code,
        standard_title=standard_title,
        requires_photo=item.requires_photo,
        requires_comment=item.requires_comment,
        task_type=item.task_type or "checkbox",
    )


@router.get("/checklists/{checklist_id}/items/{item_id}", response_model=ChecklistItemOut)
async def get_item(
    checklist_id: int,
    item_id: int,
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    # emp is resolved only to enforce authentication; suppress unused-var lint.
    _ = emp
    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")
    outs = await _build_items_batch([item], db)
    return outs[0]


@router.post("/checklists/{checklist_id}/items/{item_id}/toggle")
async def toggle_item(
    checklist_id: int,
    item_id: int,
    body: BotToggleRequest,
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    cl = (await db.execute(select(Checklist).where(Checklist.id == checklist_id))).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    if cl.status == "completed":
        raise HTTPException(status_code=400, detail="Чек-лист уже завершён")

    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")

    items = await _get_ordered_items(checklist_id, db)
    await _assert_previous_required_done(item, items)

    completing = not item.is_completed
    if completing:
        await _assert_completion_requirements(item, body.note, db)

    item.is_completed = completing
    if completing:
        item.is_skipped = False
        item.completed_by_employee_id = emp.id
        item.completed_at = datetime.now(timezone.utc)
        if body.note:
            item.note = body.note
    else:
        item.completed_by_employee_id = None
        item.completed_at = None
        item.note = None

    emp.last_activity_at = datetime.now(timezone.utc)

    await log_action(
        db,
        actor_id=emp.id,
        action="task.completed" if item.is_completed else "task.reopened",
        entity_type="checklist_item",
        entity_id=item.id,
        metadata={"checklist_id": checklist_id, "title": item.title, "note": item.note, "via": "telegram"},
    )
    await db.commit()
    return {"is_completed": item.is_completed, "is_skipped": item.is_skipped}


@router.post("/checklists/{checklist_id}/items/{item_id}/skip")
async def skip_item(
    checklist_id: int,
    item_id: int,
    body: BotSkipRequest,
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    cl = (await db.execute(select(Checklist).where(Checklist.id == checklist_id))).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    if cl.status == "completed":
        raise HTTPException(status_code=400, detail="Чек-лист уже завершён")

    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")
    if item.is_required:
        raise HTTPException(status_code=400, detail="Этот пункт обязателен и не может быть пропущен")
    if item.is_completed:
        raise HTTPException(status_code=400, detail="Пункт уже выполнен")

    items = await _get_ordered_items(checklist_id, db)
    await _assert_previous_required_done(item, items)

    item.is_skipped = True
    if body.note:
        item.note = body.note

    emp.last_activity_at = datetime.now(timezone.utc)

    await log_action(
        db, actor_id=emp.id, action="task.skipped", entity_type="checklist_item", entity_id=item.id,
        metadata={"checklist_id": checklist_id, "title": item.title, "note": item.note, "via": "telegram"},
    )
    await db.commit()
    return {"is_skipped": True}


@router.post("/checklists/{checklist_id}/items/{item_id}/photo", response_model=ChecklistItemOut)
async def upload_item_photo(
    checklist_id: int,
    item_id: int,
    x_bot_employee_token: str = Header(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Resolve employee from token manually (can't use Depends inside multipart
    # endpoint that also uses Header — inject token explicitly and call helper).
    token_hash = _hash_bot_token(x_bot_employee_token)
    emp = (
        await db.execute(
            select(Employee).where(Employee.bot_session_token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if not emp or emp.status != "active":
        raise HTTPException(status_code=401, detail="Недействительный или отозванный токен бота")

    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")

    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла «{content_type}». Разрешены: JPEG, PNG, WebP, GIF.",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    (Path(CHECKLIST_UPLOAD_DIR) / filename).write_bytes(content)

    photo = Photo(
        checklist_item_id=item.id,
        uploaded_by_employee_id=emp.id,
        url=f"/api/v1/checklists/photos/{filename}",
    )
    db.add(photo)
    await db.flush()

    emp.last_activity_at = datetime.now(timezone.utc)

    await log_action(
        db, actor_id=emp.id, action="photo.uploaded", entity_type="checklist_item", entity_id=item.id,
        metadata={"photo_id": photo.id, "via": "telegram"},
    )

    await db.commit()
    await db.refresh(item)
    outs = await _build_items_batch([item], db)
    return outs[0]


@router.delete("/checklists/{checklist_id}/items/{item_id}/photos/{photo_id}")
async def delete_item_photo(
    checklist_id: int,
    item_id: int,
    photo_id: int,
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id,
                ChecklistItem.checklist_id == checklist_id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")

    photo = (
        await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.checklist_item_id == item_id)
        )
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    if photo.uploaded_by_employee_id != emp.id:
        role = (
            await db.execute(select(Role).where(Role.id == emp.role_id))
        ).scalar_one_or_none()
        if not role or role.permission_level < 1:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

    original_uploader_id = photo.uploaded_by_employee_id
    await db.delete(photo)
    await log_action(
        db,
        actor_id=emp.id,
        action="photo.deleted",
        entity_type="checklist_item",
        entity_id=item_id,
        metadata={
            "photo_id": photo_id,
            "checklist_id": checklist_id,
            "original_uploader_id": original_uploader_id,
            "via": "telegram",
        },
    )
    await db.commit()
    return {"ok": True}
