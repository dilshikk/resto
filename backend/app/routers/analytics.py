import csv
import io
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import Checklist, ChecklistItem
from app.models.employee import Employee
from app.models.role import Role
from app.routers.checklists import _compute_deadline_status

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _default_range() -> tuple[str, str]:
    today = date.today()
    return (today - timedelta(days=29)).isoformat(), today.isoformat()


async def _branch_name_cache(branch_ids: set[int], db: AsyncSession) -> dict[int, str]:
    """Fetch names for all given branch IDs in a single query."""
    if not branch_ids:
        return {}
    rows = (await db.execute(select(Branch).where(Branch.id.in_(branch_ids)))).scalars().all()
    return {b.id: b.name for b in rows}


async def _allowed_branch_ids(current: Employee, db: AsyncSession) -> set[int] | None:
    """
    Return the set of branch IDs the caller may see, or None if unrestricted
    (supervisor / director with permission_level >= 2).
    """
    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    if role and role.permission_level >= 2:
        return None  # unrestricted
    return {current.primary_branch_id, *(current.additional_branch_ids or [])}


def _assert_branch_param_allowed(branch_id: int, allowed: set[int] | None) -> None:
    """Raise 403 if a specific branch_id filter is outside the caller's access."""
    if allowed is not None and branch_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к аналитике этого филиала",
        )


async def _get_checklists_in_range(
    db: AsyncSession,
    date_from: str,
    date_to: str,
    branch_id: int | None,
    allowed: set[int] | None,
):
    q = select(Checklist).where(
        Checklist.date >= date_from,
        Checklist.date <= date_to,
    )
    if branch_id:
        q = q.where(Checklist.branch_id == branch_id)
    elif allowed is not None:
        q = q.where(Checklist.branch_id.in_(allowed))
    return (await db.execute(q)).scalars().all()


async def _items_for_checklists(checklist_ids: list[int], db: AsyncSession):
    if not checklist_ids:
        return []
    q = select(ChecklistItem).where(ChecklistItem.checklist_id.in_(checklist_ids))
    return (await db.execute(q)).scalars().all()


def _deadline_stats(cls: list[Checklist]) -> dict[str, int]:
    """
    Count checklists by deadline_status for those that have a due_at set.
    Returns: on_time, overdue, not_completed, no_deadline counts.
    """
    on_time = overdue = not_completed = no_deadline = 0
    for c in cls:
        status = _compute_deadline_status(c)
        if status is None:
            no_deadline += 1
        elif status == "ON_TIME":
            on_time += 1
        elif status == "OVERDUE":
            overdue += 1
        elif status == "NOT_COMPLETED":
            not_completed += 1
    return {
        "on_time": on_time,
        "overdue": overdue,
        "not_completed": not_completed,
        "no_deadline": no_deadline,
    }


def _avg_completion_minutes(cls: list[Checklist]) -> float | None:
    """Average minutes from started_at to completed_at for completed checklists."""
    durations = [
        (c.completed_at - c.started_at).total_seconds() / 60
        for c in cls
        if c.status == "completed" and c.started_at and c.completed_at
    ]
    return round(sum(durations) / len(durations), 1) if durations else None


# ── summary ─────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    allowed = await _allowed_branch_ids(current, db)
    if branch_id is not None:
        _assert_branch_param_allowed(branch_id, allowed)

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id, allowed)
    ids = [c.id for c in cls]
    items = await _items_for_checklists(ids, db)

    total_cls = len(cls)
    completed_cls = sum(1 for c in cls if c.status == "completed")
    total_items = len(items)
    completed_items = sum(1 for i in items if i.is_completed)
    required_items = [i for i in items if i.is_required]
    missed_required = sum(1 for i in required_items if not i.is_completed)

    dl_stats = _deadline_stats(cls)
    avg_min = _avg_completion_minutes(cls)
    on_time_pct = (
        round(dl_stats["on_time"] / (total_cls - dl_stats["no_deadline"]) * 100)
        if (total_cls - dl_stats["no_deadline"]) > 0
        else None
    )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_checklists": total_cls,
        "completed_checklists": completed_cls,
        "checklist_completion_pct": round(completed_cls / total_cls * 100) if total_cls else 0,
        "total_items": total_items,
        "completed_items": completed_items,
        "item_completion_pct": round(completed_items / total_items * 100) if total_items else 0,
        "missed_required_items": missed_required,
        # Deadline metrics
        "deadline": {
            "on_time": dl_stats["on_time"],
            "overdue": dl_stats["overdue"],
            "not_completed": dl_stats["not_completed"],
            "no_deadline": dl_stats["no_deadline"],
            "on_time_pct": on_time_pct,
            "avg_completion_minutes": avg_min,
        },
    }


# ── by-day ──────────────────────────────────────────────────────────────────

@router.get("/by-day")
async def get_by_day(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    allowed = await _allowed_branch_ids(current, db)
    if branch_id is not None:
        _assert_branch_param_allowed(branch_id, allowed)

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id, allowed)

    by_date: dict[str, list] = defaultdict(list)
    for c in cls:
        by_date[c.date].append(c)

    d = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    result = []
    while d <= end:
        ds = d.isoformat()
        day_cls = by_date.get(ds, [])
        total = len(day_cls)
        completed = sum(1 for c in day_cls if c.status == "completed")
        dl = _deadline_stats(day_cls)
        result.append({
            "date": ds,
            "total": total,
            "completed": completed,
            "pct": round(completed / total * 100) if total else 0,
            "on_time": dl["on_time"],
            "overdue": dl["overdue"],
            "not_completed": dl["not_completed"],
        })
        d += timedelta(days=1)

    return result


# ── branches ranking ────────────────────────────────────────────────────────────

@router.get("/branches")
async def get_branches_ranking(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    allowed = await _allowed_branch_ids(current, db)
    cls = await _get_checklists_in_range(db, date_from, date_to, None, allowed)

    branch_cls: dict[int, list] = defaultdict(list)
    for c in cls:
        branch_cls[c.branch_id].append(c)

    name_cache = await _branch_name_cache(set(branch_cls.keys()), db)

    result = []
    for bid, items in branch_cls.items():
        total = len(items)
        completed = sum(1 for c in items if c.status == "completed")
        dl = _deadline_stats(items)
        result.append({
            "branch_id": bid,
            "branch_name": name_cache.get(bid, str(bid)),
            "total": total,
            "completed": completed,
            "pct": round(completed / total * 100) if total else 0,
            "on_time": dl["on_time"],
            "overdue": dl["overdue"],
            "not_completed": dl["not_completed"],
        })

    result.sort(key=lambda x: x["pct"], reverse=True)
    return result


# ── violations (top uncompleted required items) ────────────────────────────────

@router.get("/violations")
async def get_violations(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    limit: int = Query(default=10, le=50),
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    allowed = await _allowed_branch_ids(current, db)
    if branch_id is not None:
        _assert_branch_param_allowed(branch_id, allowed)

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id, allowed)
    ids = [c.id for c in cls]
    items = await _items_for_checklists(ids, db)

    counter: Counter[str] = Counter()
    for item in items:
        if item.is_required and not item.is_completed:
            counter[item.title] += 1

    return [
        {"title": title, "count": count}
        for title, count in counter.most_common(limit)
    ]


# ── CSV export ─────────────────────────────────────────────────────────────────

@router.get("/export-csv")
async def export_csv(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    allowed = await _allowed_branch_ids(current, db)
    if branch_id is not None:
        _assert_branch_param_allowed(branch_id, allowed)

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id, allowed)

    cl_map = {c.id: c for c in cls}
    ids = list(cl_map.keys())
    items = await _items_for_checklists(ids, db)

    branch_cache = await _branch_name_cache({c.branch_id for c in cls}, db)

    STATUS_LABELS = {
        "ON_TIME": "В срок",
        "OVERDUE": "Просрочено",
        "NOT_COMPLETED": "Не выполнено",
    }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Дата", "Филиал", "Шаблон", "Смена", "Статус чек-листа",
        "Дедлайн", "Статус дедлайна",
        "Пункт", "Обязательный", "Выполнен", "Выполнил", "Время выполнения", "Заметка",
    ])

    shift_labels = {"morning": "Утро", "afternoon": "День", "evening": "Вечер"}

    for item in items:
        cl = cl_map[item.checklist_id]
        dl_status = _compute_deadline_status(cl)
        writer.writerow([
            cl.date,
            branch_cache.get(cl.branch_id, str(cl.branch_id)),
            cl.template_name,
            shift_labels.get(cl.shift, cl.shift),
            "Завершён" if cl.status == "completed" else "Открыт",
            cl.due_at.isoformat() if cl.due_at else "",
            STATUS_LABELS.get(dl_status, "") if dl_status else "",
            item.title,
            "Да" if item.is_required else "Нет",
            "Да" if item.is_completed else "Нет",
            "",  # completed_by — see TZ item 3.4
            item.completed_at.isoformat() if item.completed_at else "",
            item.note or "",
        ])

    output.seek(0)
    filename = f"mado_report_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
