import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_user
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import Checklist, ChecklistItem
from app.models.employee import Employee

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _default_range() -> tuple[str, str]:
    today = date.today()
    return (today - timedelta(days=29)).isoformat(), today.isoformat()


async def _branch_name(branch_id: int, db: AsyncSession) -> str:
    b = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one_or_none()
    return b.name if b else str(branch_id)


async def _get_checklists_in_range(
    db: AsyncSession,
    date_from: str,
    date_to: str,
    branch_id: int | None,
):
    q = select(Checklist).where(
        Checklist.date >= date_from,
        Checklist.date <= date_to,
    )
    if branch_id:
        q = q.where(Checklist.branch_id == branch_id)
    return (await db.execute(q)).scalars().all()


async def _items_for_checklists(checklist_ids: list[int], db: AsyncSession):
    if not checklist_ids:
        return []
    q = select(ChecklistItem).where(ChecklistItem.checklist_id.in_(checklist_ids))
    return (await db.execute(q)).scalars().all()


# ── summary ─────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id)
    ids = [c.id for c in cls]
    items = await _items_for_checklists(ids, db)

    total_cls = len(cls)
    completed_cls = sum(1 for c in cls if c.status == "completed")
    total_items = len(items)
    completed_items = sum(1 for i in items if i.is_completed)
    required_items = [i for i in items if i.is_required]
    missed_required = sum(1 for i in required_items if not i.is_completed)

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
    }


# ── by-day ──────────────────────────────────────────────────────────────────

@router.get("/by-day")
async def get_by_day(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    branch_id: int | None = Query(default=None),
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id)

    # group by date
    from collections import defaultdict
    by_date: dict[str, list] = defaultdict(list)
    for c in cls:
        by_date[c.date].append(c)

    # fill all days in range
    d = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    result = []
    while d <= end:
        ds = d.isoformat()
        day_cls = by_date.get(ds, [])
        total = len(day_cls)
        completed = sum(1 for c in day_cls if c.status == "completed")
        result.append({
            "date": ds,
            "total": total,
            "completed": completed,
            "pct": round(completed / total * 100) if total else 0,
        })
        d += timedelta(days=1)

    return result


# ── branches ranking ────────────────────────────────────────────────────────────

@router.get("/branches")
async def get_branches_ranking(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    cls = await _get_checklists_in_range(db, date_from, date_to, None)

    from collections import defaultdict
    branch_cls: dict[int, list] = defaultdict(list)
    for c in cls:
        branch_cls[c.branch_id].append(c)

    result = []
    for branch_id, items in branch_cls.items():
        total = len(items)
        completed = sum(1 for c in items if c.status == "completed")
        result.append({
            "branch_id": branch_id,
            "branch_name": await _branch_name(branch_id, db),
            "total": total,
            "completed": completed,
            "pct": round(completed / total * 100) if total else 0,
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
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id)
    ids = [c.id for c in cls]
    items = await _items_for_checklists(ids, db)

    from collections import Counter
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
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range()

    cls = await _get_checklists_in_range(db, date_from, date_to, branch_id)

    # collect all items with checklist meta
    cl_map = {c.id: c for c in cls}
    ids = list(cl_map.keys())
    items = await _items_for_checklists(ids, db)

    # branch name cache
    branch_cache: dict[int, str] = {}
    for c in cls:
        if c.branch_id not in branch_cache:
            branch_cache[c.branch_id] = await _branch_name(c.branch_id, db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Дата", "Филиал", "Шаблон", "Смена", "Статус чек-листа",
        "Пункт", "Обязательный", "Выполнен", "Выполнил", "Время выполнения", "Заметка",
    ])

    shift_labels = {"morning": "Утро", "afternoon": "День", "evening": "Вечер"}

    for item in items:
        cl = cl_map[item.checklist_id]
        writer.writerow([
            cl.date,
            branch_cache.get(cl.branch_id, str(cl.branch_id)),
            cl.template_name,
            shift_labels.get(cl.shift, cl.shift),
            "Завершён" if cl.status == "completed" else "Открыт",
            item.title,
            "Да" if item.is_required else "Нет",
            "Да" if item.is_completed else "Нет",
            "",  # completed_by (skip for now)
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
