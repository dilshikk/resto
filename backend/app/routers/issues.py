import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.issue import Issue, IssueComment
from app.schemas.issue import (
    IssueCreate,
    IssueOut,
    IssueDetail,
    IssueCommentCreate,
    IssueCommentOut,
    IssueStatusUpdate,
)

router = APIRouter(prefix="/issues", tags=["issues"])

UPLOAD_DIR = Path("/tmp/mado_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── helpers ─────────────────────────────────────────────────────────────────

async def _emp_name(emp_id: int | None, db: AsyncSession) -> str | None:
    if not emp_id:
        return None
    e = (await db.execute(select(Employee).where(Employee.id == emp_id))).scalar_one_or_none()
    return e.full_name if e else None


async def _branch_name(branch_id: int, db: AsyncSession) -> str:
    b = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one_or_none()
    return b.name if b else str(branch_id)


async def _comment_count(issue_id: int, db: AsyncSession) -> int:
    result = await db.execute(select(IssueComment).where(IssueComment.issue_id == issue_id))
    return len(result.scalars().all())


async def _build_out(issue: Issue, db: AsyncSession) -> IssueOut:
    return IssueOut(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        branch_id=issue.branch_id,
        branch_name=await _branch_name(issue.branch_id, db),
        category=issue.category,
        priority=issue.priority,
        status=issue.status,
        photo_urls=issue.photo_urls or [],
        reported_by_name=await _emp_name(issue.reported_by_employee_id, db) or "—",
        assigned_to_name=await _emp_name(issue.assigned_to_employee_id, db),
        resolved_at=issue.resolved_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        comment_count=await _comment_count(issue.id, db),
    )


# ── photo upload ───────────────────────────────────────────────────────────

@router.post("/upload-photo")
async def upload_photo(
    file: UploadFile = File(...),
    _: Employee = Depends(get_current_user),
):
    """Save photo to /tmp and return a server-relative URL."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Только изображения")
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / filename
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (max 8 MB)")
    dest.write_bytes(content)
    return {"url": f"/api/v1/issues/photos/{filename}"}


@router.get("/photos/{filename}")
async def get_photo(filename: str, _: Employee = Depends(get_current_user)):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return FileResponse(str(path))


# ── CRUD ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[IssueOut])
async def list_issues(
    status: str | None = None,
    branch_id: int | None = None,
    priority: str | None = None,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Issue).order_by(Issue.created_at.desc())
    if status:
        q = q.where(Issue.status == status)
    if branch_id:
        q = q.where(Issue.branch_id == branch_id)
    if priority:
        q = q.where(Issue.priority == priority)

    issues = (await db.execute(q)).scalars().all()
    return [await _build_out(i, db) for i in issues]


@router.post("", response_model=IssueOut)
async def create_issue(
    data: IssueCreate,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="Заголовок обязателен")
    issue = Issue(
        title=data.title.strip(),
        description=data.description,
        branch_id=data.branch_id,
        category=data.category,
        priority=data.priority,
        status="open",
        photo_urls=data.photo_urls,
        reported_by_employee_id=current.id,
        checklist_id=data.checklist_id,
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return await _build_out(issue, db)


@router.get("/{issue_id}", response_model=IssueDetail)
async def get_issue(
    issue_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = (await db.execute(select(Issue).where(Issue.id == issue_id))).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Инцидент не найден")

    comments_res = await db.execute(
        select(IssueComment)
        .where(IssueComment.issue_id == issue_id)
        .order_by(IssueComment.created_at)
    )
    comments = comments_res.scalars().all()
    comment_outs = []
    for c in comments:
        comment_outs.append(IssueCommentOut(
            id=c.id,
            issue_id=c.issue_id,
            author_name=await _emp_name(c.author_employee_id, db) or "—",
            text=c.text,
            created_at=c.created_at,
        ))

    base = await _build_out(issue, db)
    return IssueDetail(**base.model_dump(), comments=comment_outs)


@router.patch("/{issue_id}/status", response_model=IssueOut)
async def update_status(
    issue_id: int,
    data: IssueStatusUpdate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    VALID = {"open", "in_progress", "closed"}
    if data.status not in VALID:
        raise HTTPException(status_code=400, detail=f"Статус должен быть одним из: {', '.join(VALID)}")

    issue = (await db.execute(select(Issue).where(Issue.id == issue_id))).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Инцидент не найден")

    issue.status = data.status
    if data.assigned_to_employee_id is not None:
        issue.assigned_to_employee_id = data.assigned_to_employee_id
    if data.status == "closed" and not issue.resolved_at:
        issue.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(issue)
    return await _build_out(issue, db)


@router.post("/{issue_id}/comments", response_model=IssueCommentOut)
async def add_comment(
    issue_id: int,
    data: IssueCommentCreate,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = (await db.execute(select(Issue).where(Issue.id == issue_id))).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    c = IssueComment(
        issue_id=issue_id,
        author_employee_id=current.id,
        text=data.text.strip(),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return IssueCommentOut(
        id=c.id,
        issue_id=c.issue_id,
        author_name=await _emp_name(c.author_employee_id, db) or "—",
        text=c.text,
        created_at=c.created_at,
    )
