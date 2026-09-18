from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import ChecklistTemplate, ChecklistTemplateItem, Checklist, ChecklistItem
from app.models.employee import Employee
from app.models.role import Role
from app.schemas.checklist import (
    ChecklistCreate,
    ChecklistOut,
    ChecklistDetail,
    ChecklistItemOut,
    ToggleItemRequest,
)

router = APIRouter(prefix="/checklists", tags=["checklists"])


async def _build_out(cl: Checklist, db: AsyncSession) -> ChecklistOut:
    branch = (
        await db.execute(select(Branch).where(Branch.id == cl.branch_id))
    ).scalar_one_or_none()
    items_res = await db.execute(
        select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id)
    )
    items = items_res.scalars().all()
    return ChecklistOut(
        id=cl.id,
        template_id=cl.template_id,
        template_name=cl.template_name,
        branch_id=cl.branch_id,
        branch_name=branch.name if branch else "—",
        shift=cl.shift,
        date=cl.date,
        status=cl.status,
        total_items=len(items),
        completed_items=sum(1 for i in items if i.is_completed),
        created_at=cl.created_at,
    )


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

    result = await db.execute(query)
    all_cls = result.scalars().all()

    role = (
        await db.execute(select(Role).where(Role.id == current.role_id))
    ).scalar_one_or_none()
    is_supervisor = role and role.permission_level >= 2

    allowed = {current.primary_branch_id, *(current.additional_branch_ids or [])}

    return [
        await _build_out(cl, db)
        for cl in all_cls
        if is_supervisor or cl.branch_id in allowed
    ]


@router.post("", response_model=ChecklistOut)
async def create_checklist(
    data: ChecklistCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    tpl = (
        await db.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == data.template_id,
                ChecklistTemplate.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    cl = Checklist(
        template_id=tpl.id,
        template_name=tpl.name,
        branch_id=data.branch_id,
        shift=data.shift,
        date=data.date,
        status="open",
        created_by_employee_id=current.id,
    )
    db.add(cl)
    await db.flush()

    items_res = await db.execute(
        select(ChecklistTemplateItem)
        .where(ChecklistTemplateItem.template_id == tpl.id)
        .order_by(ChecklistTemplateItem.sort_order)
    )
    for ti in items_res.scalars().all():
        db.add(
            ChecklistItem(
                checklist_id=cl.id,
                title=ti.title,
                description=ti.description,
                is_required=ti.is_required,
                sort_order=ti.sort_order,
            )
        )

    await db.commit()
    await db.refresh(cl)
    return await _build_out(cl, db)


@router.get("/{checklist_id}", response_model=ChecklistDetail)
async def get_checklist(
    checklist_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = (
        await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    ).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")

    branch = (
        await db.execute(select(Branch).where(Branch.id == cl.branch_id))
    ).scalar_one_or_none()

    items_res = await db.execute(
        select(ChecklistItem)
        .where(ChecklistItem.checklist_id == cl.id)
        .order_by(ChecklistItem.sort_order)
    )
    items = items_res.scalars().all()

    item_outs = []
    for item in items:
        completed_by_name = None
        if item.completed_by_employee_id:
            emp = (
                await db.execute(
                    select(Employee).where(Employee.id == item.completed_by_employee_id)
                )
            ).scalar_one_or_none()
            completed_by_name = emp.full_name if emp else None

        item_outs.append(
            ChecklistItemOut(
                id=item.id,
                checklist_id=item.checklist_id,
                title=item.title,
                description=item.description,
                is_required=item.is_required,
                sort_order=item.sort_order,
                is_completed=item.is_completed,
                completed_by_name=completed_by_name,
                completed_at=item.completed_at,
                note=item.note,
            )
        )

    return ChecklistDetail(
        id=cl.id,
        template_id=cl.template_id,
        template_name=cl.template_name,
        branch_id=cl.branch_id,
        branch_name=branch.name if branch else "—",
        shift=cl.shift,
        date=cl.date,
        status=cl.status,
        total_items=len(items),
        completed_items=sum(1 for i in items if i.is_completed),
        created_at=cl.created_at,
        items=item_outs,
    )


@router.patch("/{checklist_id}/items/{item_id}/toggle")
async def toggle_item(
    checklist_id: int,
    item_id: int,
    body: ToggleItemRequest,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cl = (
        await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    ).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
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

    item.is_completed = not item.is_completed
    if item.is_completed:
        item.completed_by_employee_id = current.id
        item.completed_at = datetime.now(timezone.utc)
        if body.note:
            item.note = body.note
    else:
        item.completed_by_employee_id = None
        item.completed_at = None
        item.note = None

    await db.commit()
    return {"is_completed": item.is_completed}


@router.post("/{checklist_id}/complete")
async def complete_checklist(
    checklist_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    cl = (
        await db.execute(select(Checklist).where(Checklist.id == checklist_id))
    ).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    cl.status = "completed"
    await db.commit()
    return {"ok": True}
