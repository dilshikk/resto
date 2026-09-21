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
    PhotoListItem,
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


# ── Deadline helpers ────────────────────────────────────────────────────────

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


# ── Access guards ───────────────────────────────────────────────────────────

async def _assert_branch_access(cl: Checklist, current: Employee, db: AsyncSession) -> None:
    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    if role and role.can_access_all_branches:
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


# ── Builders ────────────────────────────────────────────────────────────────

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
                title_uz=item.title_uz,
                title_en=item.title_en,
                description=item.description,
                description_uz=item.description_uz,
                description_en=item.description_en,
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


# ── Ordering / step helpers ─────────────────────────────────────────────────

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
                    f"«{other.title}» (шаг {other.sort_order + 1})"
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
            detail="Обязательно добавьте комментарий",
        )
    if item.requires_photo:
        photos = (
            await db.execute(
                select(Photo).where(Photo.checklist_item_id == item.id)
            )
        ).scalars().all()
        if not photos:
            raise HTTPException(
                status_code=400,
                detail="Обязательно загрузите фото",
            )


# ── Current-item helper ──────────────────────────────────────────────────────────────

async def _build_current_item(
    checklist_id: int,
    db: AsyncSession,
) -> CurrentItemOut | None:
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


# ── Step-by-step: complete a single item ─────────────────────────────────────────────

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


# ── Step-by-step: skip an optional item ─────────────────────────────────────────────

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


# ── Complete the whole checklist ───────────────────────────────────────────────────

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
        titles = ", ".join(f"«{i.title}»" for i in pending_required[:3])
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


# ── Photo list (for the Photos report page) ────────────────────────────────────────

@router.get("/photos", response_model=list[PhotoListItem])
async def list_photos(
    branch_id: int | None = Query(None),
    date_from: str | None = Query(None, description="YYYY-MM-DD, inclusive"),
    date_to: str | None = Query(None, description="YYYY-MM-DD, inclusive"),
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PhotoListItem]:
    """
    Return all photos the current employee is allowed to see, optionally
    filtered by branch and/or date range of the parent checklist.

    Access rules:
      - Employees with can_access_all_branches=True see every photo.
      - Everyone else only sees photos from their own branches.
      - Passing branch_id further narrows the result.
    """
    # 1. Resolve which branches the employee may access.
    role = await _get_role(current, db)
    can_all = bool(role and role.can_access_all_branches)
    allowed_branch_ids: set[int] | None = None
    if not can_all:
        allowed_branch_ids = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    # 2. Load all photos with their checklist-item and checklist context.
    #    We do this in three batch queries to avoid a heavy SQL JOIN.
    photos: list[Photo] = (
        await db.execute(select(Photo).order_by(Photo.created_at.desc()))
    ).scalars().all()

    if not photos:
        return []

    # 3. Batch-load checklist items.
    item_ids = list({p.checklist_item_id for p in photos})
    items_map: dict[int, ChecklistItem] = {
        i.id: i
        for i in (
            await db.execute(select(ChecklistItem).where(ChecklistItem.id.in_(item_ids)))
        ).scalars().all()
    }

    # 4. Batch-load checklists.
    checklist_ids = list({i.checklist_id for i in items_map.values()})
    checklists_map: dict[int, Checklist] = {
        cl.id: cl
        for cl in (
            await db.execute(select(Checklist).where(Checklist.id.in_(checklist_ids)))
        ).scalars().all()
    }

    # 5. Batch-load branches.
    branch_ids_used = list({cl.branch_id for cl in checklists_map.values()})
    branches_map: dict[int, Branch] = {
        b.id: b
        for b in (
            await db.execute(select(Branch).where(Branch.id.in_(branch_ids_used)))
        ).scalars().all()
    }

    # 6. Batch-load photo uploaders.
    uploader_ids = list({p.uploaded_by_employee_id for p in photos if p.uploaded_by_employee_id})
    uploaders_map: dict[int, str] = {
        e.id: e.full_name
        for e in (
            await db.execute(select(Employee).where(Employee.id.in_(uploader_ids)))
        ).scalars().all()
    }

    # 7. Assemble and apply filters.
    result: list[PhotoListItem] = []
    for photo in photos:
        item = items_map.get(photo.checklist_item_id)
        if item is None:
            continue
        cl = checklists_map.get(item.checklist_id)
        if cl is None:
            continue
        branch = branches_map.get(cl.branch_id)
        if branch is None:
            continue

        # Branch-access filter
        if allowed_branch_ids is not None and cl.branch_id not in allowed_branch_ids:
            continue
        if branch_id is not None and cl.branch_id != branch_id:
            continue

        # Date-range filter (compares YYYY-MM-DD strings lexicographically — safe for ISO dates)
        if date_from and cl.date < date_from:
            continue
        if date_to and cl.date > date_to:
            continue

        result.append(
            PhotoListItem(
                id=photo.id,
                checklist_id=cl.id,
                checklist_name=cl.template_name,
                item_id=item.id,
                item_title=item.title,
                branch_id=branch.id,
                branch_name=branch.name,
                shift=cl.shift,
                date=cl.date,
                uploaded_by_name=uploaders_map.get(photo.uploaded_by_employee_id, "—"),
                url=photo.url,
                created_at=photo.created_at,
            )
        )

    return result


# ── Photo upload ──────────────────────────────────────────────────────────────────

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
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    # 1. Path-traversal guard.
    resolved = (UPLOAD_DIR / filename).resolve()
    if not str(resolved).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено")

    # 2. Branch-access check: Photo → ChecklistItem → Checklist.
    expected_url = f"/api/v1/checklists/photos/{filename}"
    photo = (
        await db.execute(select(Photo).where(Photo.url == expected_url))
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    item = (
        await db.execute(
            select(ChecklistItem).where(ChecklistItem.id == photo.checklist_item_id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    cl = await _get_checklist_or_404(item.checklist_id, db)
    await _assert_branch_access(cl, current, db)

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
