import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_manager
from app.config import settings
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import ChecklistTemplate, ChecklistTemplateItem, Checklist, ChecklistItem
from app.models.employee import Employee
from app.models.photo import Photo
from app.models.role import Role
from app.models.standard import Standard
from app.routers.audit_logs import log_action
from app.schemas.checklist import (
    ChecklistCreate,
    ChecklistOut,
    ChecklistDetail,
    ChecklistItemOut,
    ChecklistItemPhotoOut,
    CurrentItemOut,
    SkipItemRequest,
    ToggleItemRequest,
)

router = APIRouter(prefix="/checklists", tags=["checklists"])

UPLOAD_DIR = Path(settings.PHOTOS_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_PHOTO_TOKEN_TTL_SECONDS = 3600  # 1 hour


def _make_photo_token(filename: str) -> tuple[str, int]:
    """Return (token_string, expires_at_unix)."""
    expires_at = int(time.time()) + _PHOTO_TOKEN_TTL_SECONDS
    msg = f"{filename}:{expires_at}".encode()
    mac = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
    return f"{expires_at}.{mac}", expires_at


def _verify_photo_token(filename: str, token: str) -> None:
    try:
        expires_str, mac = token.split(".", 1)
        expires_at = int(expires_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=403, detail="Недействительный токен фото")

    if int(time.time()) > expires_at:
        raise HTTPException(status_code=403, detail="Токен фото истёк. Обновите страницу.")

    msg = f"{filename}:{expires_at}".encode()
    expected = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, mac):
        raise HTTPException(status_code=403, detail="Недействительный токен фото")


# ── Deadline helpers ──────────────────────────────────────────────────────────

def _compute_deadline_status(cl: Checklist) -> str | None:
    if cl.due_at is None:
        return None

    now = datetime.now(timezone.utc)

    if cl.completed_at is not None:
        if cl.completed_at <= cl.due_at:
            return "ON_TIME"
        return "OVERDUE"

    if now <= cl.due_at:
        return None

    if now > cl.due_at + timedelta(hours=24):
        return "NOT_COMPLETED"

    return "OVERDUE"


# ── Access guards ─────────────────────────────────────────────────────────────

async def _assert_branch_access(cl: Checklist, current: Employee, db: AsyncSession) -> None:
    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    if role and role.permission_level >= 2:
        return
    allowed = {current.primary_branch_id, *(current.additional_branch_ids or [])}
    if cl.branch_id not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к чек-листу другого филиала")


async def _get_checklist_or_404(checklist_id: int, db: AsyncSession) -> Checklist:
    cl = (
        await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    ).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    return cl


async def _get_role(employee: Employee, db: AsyncSession) -> Role | None:
    return (
        await db.execute(select(Role).where(Role.id == employee.role_id))
    ).scalar_one_or_none()


# ── Builders ──────────────────────────────────────────────────────────────────

def _make_checklist_out(
    cl: Checklist,
    branch_name: str,
    total: int,
    completed: int,
    skipped: int,
) -> ChecklistOut:
    return ChecklistOut(
        id=cl.id,
        template_id=cl.template_id,
        template_name=cl.template_name,
        branch_id=cl.branch_id,
        branch_name=branch_name,
        shift=cl.shift,
        date=cl.date,
        status=cl.status,
        total_items=total,
        completed_items=completed,
        skipped_items=skipped,
        created_at=cl.created_at,
        started_at=cl.started_at,
        due_at=cl.due_at,
        completed_at=cl.completed_at,
        deadline_status=_compute_deadline_status(cl),
    )


async def _build_out(cl: Checklist, db: AsyncSession) -> ChecklistOut:
    """Single-checklist builder used after create (no list context)."""
    branch = (
        await db.execute(select(Branch).where(Branch.id == cl.branch_id))
    ).scalar_one_or_none()
    items = (
        await db.execute(select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id))
    ).scalars().all()
    return _make_checklist_out(
        cl,
        branch.name if branch else "—",
        len(items),
        sum(1 for i in items if i.is_completed),
        sum(1 for i in items if i.is_skipped),
    )


async def _build_items_batch(
    items: list[ChecklistItem],
    db: AsyncSession,
) -> list[ChecklistItemOut]:
    """
    Build ChecklistItemOut for all items in a single checklist using
    batch queries instead of per-item round-trips.
    """
    if not items:
        return []

    # 1. batch-load employees that completed items
    completer_ids = {i.completed_by_employee_id for i in items if i.completed_by_employee_id}
    completers: dict[int, str] = {}
    if completer_ids:
        completers = {
            e.id: e.full_name
            for e in (
                await db.execute(select(Employee).where(Employee.id.in_(completer_ids)))
            ).scalars().all()
        }

    # 2. batch-load all photos for these items
    item_ids = [i.id for i in items]
    all_photos = (
        await db.execute(
            select(Photo)
            .where(Photo.checklist_item_id.in_(item_ids))
            .order_by(Photo.checklist_item_id, Photo.created_at)
        )
    ).scalars().all()

    # 3. batch-load photo uploaders
    uploader_ids = {p.uploaded_by_employee_id for p in all_photos if p.uploaded_by_employee_id}
    uploaders: dict[int, str] = {}
    if uploader_ids:
        uploaders = {
            e.id: e.full_name
            for e in (
                await db.execute(select(Employee).where(Employee.id.in_(uploader_ids)))
            ).scalars().all()
        }

    photos_by_item: dict[int, list[Photo]] = {}
    for p in all_photos:
        photos_by_item.setdefault(p.checklist_item_id, []).append(p)

    # 4. batch-load standards
    standard_codes = {i.standard_code for i in items if i.standard_code}
    standards: dict[str, str] = {}
    if standard_codes:
        standards = {
            s.code: s.title
            for s in (
                await db.execute(select(Standard).where(Standard.code.in_(standard_codes)))
            ).scalars().all()
        }

    # 5. assemble
    result = []
    for item in items:
        item_photos = [
            ChecklistItemPhotoOut(
                id=p.id,
                url=p.url,
                uploaded_by_name=uploaders.get(p.uploaded_by_employee_id, "—"),
                created_at=p.created_at,
            )
            for p in photos_by_item.get(item.id, [])
        ]
        result.append(
            ChecklistItemOut(
                id=item.id,
                checklist_id=item.checklist_id,
                title=item.title,
                title_uz=getattr(item, "title_uz", None),
                title_en=getattr(item, "title_en", None),
                description=item.description,
                description_uz=getattr(item, "description_uz", None),
                description_en=getattr(item, "description_en", None),
                is_required=item.is_required,
                sort_order=item.sort_order,
                is_completed=item.is_completed,
                is_skipped=item.is_skipped,
                completed_by_name=completers.get(item.completed_by_employee_id) if item.completed_by_employee_id else None,
                completed_at=item.completed_at,
                note=item.note,
                photos=item_photos,
                standard_code=item.standard_code,
                standard_title=standards.get(item.standard_code) if item.standard_code else None,
                requires_photo=item.requires_photo,
                requires_comment=item.requires_comment,
            )
        )
    return result


# ── Ordering / step helpers ───────────────────────────────────────────────────

async def _get_ordered_items(checklist_id: int, db: AsyncSession) -> list[ChecklistItem]:
    res = await db.execute(
        select(ChecklistItem)
        .where(ChecklistItem.checklist_id == checklist_id)
        .order_by(ChecklistItem.sort_order, ChecklistItem.id)
    )
    return list(res.scalars().all())


def _is_item_pending(item: ChecklistItem) -> bool:
    return not item.is_completed and not item.is_skipped


def _find_current_item(items: list[ChecklistItem]) -> ChecklistItem | None:
    for item in items:
        if _is_item_pending(item):
            return item
    return None


async def _assert_previous_required_done(
    item: ChecklistItem,
    items: list[ChecklistItem],
) -> None:
    for other in items:
        if other.sort_order >= item.sort_order:
            break
        if other.is_required and _is_item_pending(other):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Нельзя пропустить шаг: сначала выполните обязательный пункт "
                    f"\u00ab{other.title}\u00bb (шаг {other.sort_order + 1})"
                ),
            )


async def _assert_completion_requirements(
    item: ChecklistItem,
    note: str | None,
    db: AsyncSession,
) -> None:
    if item.requires_comment and not (note and note.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Пункт \u00ab{item.title}\u00bb требует комментария. Добавьте описание результата.",
        )
    if item.requires_photo:
        photo_count = len(
            (
                await db.execute(
                    select(Photo).where(Photo.checklist_item_id == item.id)
                )
            ).scalars().all()
        )
        if photo_count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Пункт \u00ab{item.title}\u00bb требует фотоотчёта. Прикрепите хотя бы одно фото.",
            )


# ── List / create ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[ChecklistOut])
async def list_checklists(
    date: str | None = None,
    branch_id: int | None = None,
    status: str | None = None,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Checklist)
    if date:
        query = query.where(Checklist.date == date)
    if branch_id:
        query = query.where(Checklist.branch_id == branch_id)
    if status:
        query = query.where(Checklist.status == status)
    query = query.order_by(Checklist.date.desc(), Checklist.id.desc())

    all_cls = (await db.execute(query)).scalars().all()

    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    is_supervisor = bool(role and role.permission_level >= 2)
    allowed = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    visible = [cl for cl in all_cls if is_supervisor or cl.branch_id in allowed]
    if not visible:
        return []

    cl_ids = [cl.id for cl in visible]
    branch_ids = {cl.branch_id for cl in visible}

    branches_map: dict[int, str] = {
        b.id: b.name
        for b in (await db.execute(select(Branch).where(Branch.id.in_(branch_ids)))).scalars().all()
    }
    all_items = (
        await db.execute(select(ChecklistItem).where(ChecklistItem.checklist_id.in_(cl_ids)))
    ).scalars().all()

    items_by_cl: dict[int, list[ChecklistItem]] = {}
    for it in all_items:
        items_by_cl.setdefault(it.checklist_id, []).append(it)

    result = []
    for cl in visible:
        cl_items = items_by_cl.get(cl.id, [])
        result.append(
            _make_checklist_out(
                cl,
                branches_map.get(cl.branch_id, "—"),
                len(cl_items),
                sum(1 for i in cl_items if i.is_completed),
                sum(1 for i in cl_items if i.is_skipped),
            )
        )
    return result


@router.post("", response_model=ChecklistOut)
async def create_checklist(
    data: ChecklistCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    is_supervisor = bool(role and role.permission_level >= 2)
    allowed = {current.primary_branch_id, *(current.additional_branch_ids or [])}
    if not is_supervisor and data.branch_id not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к чек-листу другого филиала")

    tpl = (
        await db.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == data.template_id,
                ChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден или неактивен")

    tpl_items = (
        await db.execute(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.template_id == tpl.id)
            .order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.id)
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    due_at = (
        now + timedelta(minutes=tpl.deadline_offset_minutes)
        if tpl.deadline_offset_minutes
        else None
    )

    cl = Checklist(
        template_id=tpl.id,
        template_name=tpl.name,
        branch_id=data.branch_id,
        shift=data.shift,
        date=data.date,
        status="open",
        started_at=now,
        due_at=due_at,
        created_by_employee_id=current.id,
    )
    db.add(cl)
    await db.flush()

    for ti in tpl_items:
        db.add(
            ChecklistItem(
                checklist_id=cl.id,
                title=ti.title,
                title_uz=getattr(ti, "title_uz", None),
                title_en=getattr(ti, "title_en", None),
                description=ti.description,
                description_uz=getattr(ti, "description_uz", None),
                description_en=getattr(ti, "description_en", None),
                sort_order=ti.sort_order,
                is_required=ti.is_required,
                standard_code=ti.standard_code,
                requires_photo=ti.requires_photo,
                requires_comment=ti.requires_comment,
            )
        )

    await log_action(
        db,
        actor_id=current.id,
        action="checklist.created",
        entity_type="checklist",
        entity_id=cl.id,
        metadata={"template": tpl.name, "branch_id": data.branch_id, "shift": data.shift},
    )
    await db.commit()
    await db.refresh(cl)
    return await _build_out(cl, db)


# ── Detail ─────────────────────────────────────────────────────────────────────

@router.get("/{checklist_id}", response_model=ChecklistDetail)
async def get_checklist(
    checklist_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)

    branch = (
        await db.execute(select(Branch).where(Branch.id == cl.branch_id))
    ).scalar_one_or_none()

    ordered = await _get_ordered_items(checklist_id, db)
    item_outs = await _build_items_batch(ordered, db)

    return ChecklistDetail(
        id=cl.id,
        template_id=cl.template_id,
        template_name=cl.template_name,
        branch_id=cl.branch_id,
        branch_name=branch.name if branch else "—",
        shift=cl.shift,
        date=cl.date,
        status=cl.status,
        total_items=len(ordered),
        completed_items=sum(1 for i in ordered if i.is_completed),
        skipped_items=sum(1 for i in ordered if i.is_skipped),
        created_at=cl.created_at,
        started_at=cl.started_at,
        due_at=cl.due_at,
        completed_at=cl.completed_at,
        deadline_status=_compute_deadline_status(cl),
        items=item_outs,
    )


# ── Current item (step-by-step web mode) ─────────────────────────────────────

@router.get("/{checklist_id}/current-item", response_model=CurrentItemOut | None)
async def get_current_item(
    checklist_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)
    if cl.status == "completed":
        return None

    items = await _get_ordered_items(checklist_id, db)
    item = _find_current_item(items)
    if item is None:
        return None

    standard_title = None
    if item.standard_code:
        standard = (
            await db.execute(select(Standard).where(Standard.code == item.standard_code))
        ).scalar_one_or_none()
        standard_title = standard.title if standard else None

    position = next(i for i, it in enumerate(items, 1) if it.id == item.id)

    return CurrentItemOut(
        id=item.id,
        checklist_id=item.checklist_id,
        title=item.title,
        description=item.description,
        is_required=item.is_required,
        sort_order=item.sort_order,
        total_items=len(items),
        current_position=position,
        standard_code=item.standard_code,
        standard_title=standard_title,
        requires_photo=item.requires_photo,
        requires_comment=item.requires_comment,
    )


# ── Step-by-step: complete a single item ──────────────────────────────────────

@router.patch("/{checklist_id}/items/{item_id}/toggle")
async def toggle_item(
    checklist_id: int,
    item_id: int,
    body: ToggleItemRequest,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)
    if cl.status == "completed":
        raise HTTPException(status_code=400, detail="Чек-лист уже завершён")

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

    items = await _get_ordered_items(checklist_id, db)
    await _assert_previous_required_done(item, items)

    completing = not item.is_completed
    if completing:
        await _assert_completion_requirements(item, body.note, db)

    item.is_completed = completing
    if completing:
        item.is_skipped = False
        item.completed_by_employee_id = current.id
        item.completed_at = datetime.now(timezone.utc)
        if body.note:
            item.note = body.note
    else:
        item.completed_by_employee_id = None
        item.completed_at = None
        item.note = None

    await log_action(
        db,
        actor_id=current.id,
        action="task.completed" if item.is_completed else "task.reopened",
        entity_type="checklist_item",
        entity_id=item.id,
        metadata={"checklist_id": checklist_id, "title": item.title, "note": item.note},
    )
    await db.commit()
    return {"is_completed": item.is_completed, "is_skipped": item.is_skipped}


# ── Step-by-step: skip an optional item ───────────────────────────────────────

@router.post("/{checklist_id}/items/{item_id}/skip")
async def skip_item(
    checklist_id: int,
    item_id: int,
    body: SkipItemRequest,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)
    if cl.status == "completed":
        raise HTTPException(status_code=400, detail="Чек-лист уже завершён")

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

    if item.is_required:
        raise HTTPException(status_code=400, detail="Этот пункт обязателен и не может быть пропущен")
    if item.is_completed:
        raise HTTPException(status_code=400, detail="Пункт уже выполнен. Отмените выполнение перед тем, как пропустить.")

    items = await _get_ordered_items(checklist_id, db)
    await _assert_previous_required_done(item, items)

    item.is_skipped = True
    if body.note:
        item.note = body.note

    await log_action(
        db,
        actor_id=current.id,
        action="task.skipped",
        entity_type="checklist_item",
        entity_id=item.id,
        metadata={"checklist_id": checklist_id, "title": item.title, "note": item.note},
    )
    await db.commit()
    return {"is_skipped": True}


# ── Complete the whole checklist ──────────────────────────────────────────────

@router.post("/{checklist_id}/complete")
async def complete_checklist(
    checklist_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)

    if cl.status == "completed":
        raise HTTPException(status_code=400, detail="Чек-лист уже завершён")

    role = await _get_role(current, db)
    is_manager = bool(role and role.permission_level >= 1)
    if not is_manager and cl.created_by_employee_id != current.id:
        raise HTTPException(
            status_code=403,
            detail="Вы можете завершить только свой чек-лист. Обратитесь к менеджеру.",
        )

    items = await _get_ordered_items(checklist_id, db)
    pending_required = [i for i in items if i.is_required and _is_item_pending(i)]
    if pending_required:
        titles = ", ".join(f"\u00ab{i.title}\u00bb" for i in pending_required[:3])
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя завершить: не выполнены обязательные пункты: {titles}",
        )

    now = datetime.now(timezone.utc)
    cl.status = "completed"
    cl.completed_at = now

    await log_action(
        db,
        actor_id=current.id,
        action="checklist.completed",
        entity_type="checklist",
        entity_id=cl.id,
        metadata={
            "completed_at": now.isoformat(),
            "deadline_status": _compute_deadline_status(cl),
            "completed_by_manager": is_manager,
        },
    )
    await db.commit()
    return {"ok": True, "deadline_status": _compute_deadline_status(cl)}


# ── Photo upload ──────────────────────────────────────────────────────────────

@router.post("/{checklist_id}/items/{item_id}/photos", response_model=ChecklistItemPhotoOut)
async def upload_item_photo(
    checklist_id: int,
    item_id: int,
    file: UploadFile = File(...),
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)

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

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Только изображения")
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (max 8 MB)")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / filename).write_bytes(content)

    photo = Photo(
        checklist_item_id=item.id,
        uploaded_by_employee_id=current.id,
        url=f"/api/v1/checklists/photos/{filename}",
    )
    db.add(photo)
    await db.flush()

    await log_action(
        db, actor_id=current.id, action="photo.uploaded", entity_type="checklist_item", entity_id=item.id,
        metadata={"photo_id": photo.id},
    )
    await db.commit()
    await db.refresh(photo)
    return ChecklistItemPhotoOut(
        id=photo.id,
        url=photo.url,
        uploaded_by_name=current.full_name,
        created_at=photo.created_at,
    )


@router.get("/photos/{filename}/signed-url")
async def get_photo_signed_url(
    filename: str,
    _: Employee = Depends(get_current_user),
) -> dict[str, str]:
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено")

    token, expires_at = _make_photo_token(filename)
    return {
        "url": f"/api/v1/checklists/photos/{filename}?token={token}",
        "expires_at": str(expires_at),
    }


@router.get("/photos/{filename}")
async def get_item_photo(
    filename: str,
    token: str = Query(..., description="HMAC-signed photo token from /photos/{filename}/signed-url"),
) -> FileResponse:
    _verify_photo_token(filename, token)

    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено")

    return FileResponse(str(path))


@router.delete("/{checklist_id}/items/{item_id}/photos/{photo_id}")
async def delete_item_photo(
    checklist_id: int,
    item_id: int,
    photo_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = await _get_checklist_or_404(checklist_id, db)
    await _assert_branch_access(cl, current, db)

    photo = (
        await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.checklist_item_id == item_id)
        )
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    if photo.uploaded_by_employee_id != current.id:
        role = (await db.execute(select(Role).where(Role.id == current.role_id))).scalar_one_or_none()
        if not role or role.permission_level < 1:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

    await db.delete(photo)
    await log_action(
        db, actor_id=current.id, action="photo.deleted", entity_type="checklist_item", entity_id=item_id,
        metadata={"photo_id": photo_id},
    )
    await db.commit()
    return {"ok": True}
