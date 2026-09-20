"""
Endpoints used exclusively by the Telegram bot service (see /bot directory).

The bot has no per-employee JWT — instead every request carries the caller's
`telegram_id` (trusted because the bot verified it via Telegram's own auth) plus a
shared `X-Bot-Secret` header that proves the request came from our bot process and
not a random client. See app.auth.verify_bot_secret / get_employee_by_telegram_id.
"""
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_employee_by_telegram_id, verify_bot_secret
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
)
from app.models.checklist import Checklist, ChecklistItem
from app.models.standard import Standard
from app.schemas.bot import BotEmployeeOut, BotLinkRequest, BotSkipRequest, BotToggleRequest
from app.schemas.checklist import ChecklistItemOut, ChecklistOut, CurrentItemOut

router = APIRouter(
    prefix="/bot",
    tags=["bot"],
    dependencies=[Depends(verify_bot_secret)],
)

_ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_VALID_LANGS = frozenset({"ru", "uz", "en"})


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
    role = (await db.execute(select(Role).where(Role.id == emp.role_id))).scalar_one_or_none()
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


@router.post("/link", response_model=BotEmployeeOut)
async def link_telegram_account(
    body: BotLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Called on /start <code> in the bot to link a Telegram account to an employee."""
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

    target.telegram_id = body.telegram_id
    await log_action(
        db, actor_id=target.id, action="employee.telegram_linked", entity_type="employee", entity_id=target.id,
        metadata={"telegram_id": body.telegram_id},
    )
    await db.commit()
    await db.refresh(target)
    return await _to_bot_employee_out(target, db)


@router.get("/me", response_model=BotEmployeeOut)
async def get_me(telegram_id: int, db: AsyncSession = Depends(get_db)):
    emp = await get_employee_by_telegram_id(telegram_id, db)
    return await _to_bot_employee_out(emp, db)


@router.get("/checklists/today", response_model=list[ChecklistOut])
async def list_my_checklists_today(telegram_id: int, db: AsyncSession = Depends(get_db)):
    emp = await get_employee_by_telegram_id(telegram_id, db)
    today = date.today().isoformat()

    allowed = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
    result = await db.execute(
        select(Checklist).where(Checklist.date == today).order_by(Checklist.id)
    )
    all_cls = result.scalars().all()
    return [await _build_out(cl, db) for cl in all_cls if cl.branch_id in allowed]


@router.get("/checklists/{checklist_id}/current-item", response_model=CurrentItemOut | None)
async def get_my_current_item(
    checklist_id: int,
    telegram_id: int,
    lang: str = "ru",
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

    await get_employee_by_telegram_id(telegram_id, db)  # ensures linked + active
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

    # Resolve standard title
    standard_title = None
    if item.standard_code:
        standard = (
            await db.execute(select(Standard).where(Standard.code == item.standard_code))
        ).scalar_one_or_none()
        standard_title = standard.title if standard else None

    # Pick localized title and description
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
    )


@router.get("/checklists/{checklist_id}/items/{item_id}", response_model=ChecklistItemOut)
async def get_item(
    checklist_id: int,
    item_id: int,
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
):
    await get_employee_by_telegram_id(telegram_id, db)
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
    db: AsyncSession = Depends(get_db),
):
    emp = await get_employee_by_telegram_id(body.telegram_id, db)

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
    db: AsyncSession = Depends(get_db),
):
    emp = await get_employee_by_telegram_id(body.telegram_id, db)

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
    telegram_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    emp = await get_employee_by_telegram_id(telegram_id, db)

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
            detail=f"Недопустимый тип файла \u00ab{content_type}\u00bb. Разрешены: JPEG, PNG, WebP, GIF.",
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
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
):
    emp = await get_employee_by_telegram_id(telegram_id, db)

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
