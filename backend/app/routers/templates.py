from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_user, require_manager
from app.database import get_db
from app.models.branch import Branch
from app.models.checklist import ChecklistTemplate, ChecklistTemplateItem
from app.models.employee import Employee
from app.models.standard import Standard
from app.schemas.checklist import (
    TemplateCreate,
    TemplateListItem,
    TemplateDetail,
    TemplateItemCreate,
    TemplateItemOut,
)

router = APIRouter(prefix="/templates", tags=["templates"])


async def _get_or_404(template_id: int, db: AsyncSession) -> ChecklistTemplate:
    result = await db.execute(
        select(ChecklistTemplate).where(ChecklistTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return tpl


async def _branch_name(branch_id: int | None, db: AsyncSession) -> str | None:
    if not branch_id:
        return None
    b = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one_or_none()
    return b.name if b else None


async def _item_count(template_id: int, db: AsyncSession) -> int:
    result = await db.execute(
        select(ChecklistTemplateItem).where(ChecklistTemplateItem.template_id == template_id)
    )
    return len(result.scalars().all())


async def _next_sort_order(template_id: int, db: AsyncSession) -> int:
    """
    Auto-assign the next sort_order slot when the client doesn't provide one.
    Without this, every item would default to 0 and step ordering would be
    undefined/unstable (the bot's "Шаг N/M" numbering would break).
    """
    result = await db.execute(
        select(func.max(ChecklistTemplateItem.sort_order)).where(
            ChecklistTemplateItem.template_id == template_id
        )
    )
    current_max = result.scalar_one_or_none()
    return (current_max + 1) if current_max is not None else 0


async def _validate_standard_code(standard_code: str | None, db: AsyncSession) -> None:
    if not standard_code:
        return
    standard = (
        await db.execute(select(Standard).where(Standard.code == standard_code))
    ).scalar_one_or_none()
    if not standard:
        raise HTTPException(status_code=404, detail="Стандарт с таким кодом не найден")


def _build_template_list_item(tpl: ChecklistTemplate, branch_name: str | None, item_count: int) -> TemplateListItem:
    return TemplateListItem(
        id=tpl.id,
        name=tpl.name,
        description=tpl.description,
        category=tpl.category,
        branch_id=tpl.branch_id,
        branch_name=branch_name,
        is_active=tpl.is_active,
        item_count=item_count,
        deadline_offset_minutes=tpl.deadline_offset_minutes,
        created_at=tpl.created_at,
    )


@router.get("", response_model=list[TemplateListItem])
async def list_templates(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChecklistTemplate).where(ChecklistTemplate.is_active == True)  # noqa: E712
    )
    templates = result.scalars().all()
    return [
        _build_template_list_item(
            tpl,
            await _branch_name(tpl.branch_id, db),
            await _item_count(tpl.id, db),
        )
        for tpl in templates
    ]


@router.post("", response_model=TemplateListItem)
async def create_template(
    data: TemplateCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Название обязательно")
    tpl = ChecklistTemplate(
        name=data.name.strip(),
        description=data.description,
        category=data.category,
        branch_id=data.branch_id,
        deadline_offset_minutes=data.deadline_offset_minutes,
        created_by_employee_id=current.id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return _build_template_list_item(tpl, await _branch_name(tpl.branch_id, db), 0)


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tpl = await _get_or_404(template_id, db)
    items_res = await db.execute(
        select(ChecklistTemplateItem)
        .where(ChecklistTemplateItem.template_id == tpl.id)
        .order_by(ChecklistTemplateItem.sort_order, ChecklistTemplateItem.id)
    )
    items = items_res.scalars().all()
    return TemplateDetail(
        **_build_template_list_item(tpl, await _branch_name(tpl.branch_id, db), len(items)).model_dump(),
        items=[TemplateItemOut.model_validate(i) for i in items],
    )


@router.patch("/{template_id}", response_model=TemplateListItem)
async def update_template(
    template_id: int,
    data: TemplateCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    tpl = await _get_or_404(template_id, db)
    tpl.name = data.name.strip()
    tpl.description = data.description
    tpl.category = data.category
    tpl.branch_id = data.branch_id
    tpl.deadline_offset_minutes = data.deadline_offset_minutes
    await db.commit()
    await db.refresh(tpl)
    return _build_template_list_item(
        tpl,
        await _branch_name(tpl.branch_id, db),
        await _item_count(tpl.id, db),
    )


@router.delete("/{template_id}")
async def deactivate_template(
    template_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    tpl = await _get_or_404(template_id, db)
    tpl.is_active = False
    await db.commit()
    return {"ok": True}


@router.post("/{template_id}/items", response_model=TemplateItemOut)
async def add_item(
    template_id: int,
    data: TemplateItemCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(template_id, db)
    await _validate_standard_code(data.standard_code, db)
    # Use None-check so sort_order=0 is treated as a valid explicit first position,
    # not as "not provided". The old `if data.sort_order` falsy check silently
    # discarded 0 and auto-assigned the next slot instead.
    sort_order = data.sort_order if data.sort_order is not None else await _next_sort_order(template_id, db)
    item = ChecklistTemplateItem(
        template_id=template_id,
        title=data.title.strip(),
        description=data.description,
        sort_order=sort_order,
        is_required=data.is_required,
        standard_code=data.standard_code,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return TemplateItemOut.model_validate(item)


@router.patch("/{template_id}/items/{item_id}", response_model=TemplateItemOut)
async def update_item(
    template_id: int,
    item_id: int,
    data: TemplateItemCreate,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    await _validate_standard_code(data.standard_code, db)
    item = (
        await db.execute(
            select(ChecklistTemplateItem).where(
                ChecklistTemplateItem.id == item_id,
                ChecklistTemplateItem.template_id == template_id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")

    item.title = data.title.strip()
    item.description = data.description
    item.sort_order = data.sort_order
    item.is_required = data.is_required
    item.standard_code = data.standard_code

    await db.commit()
    await db.refresh(item)
    return TemplateItemOut.model_validate(item)


@router.delete("/{template_id}/items/{item_id}")
async def remove_item(
    template_id: int,
    item_id: int,
    current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChecklistTemplateItem).where(
            ChecklistTemplateItem.id == item_id,
            ChecklistTemplateItem.template_id == template_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")
    await db.delete(item)
    await db.commit()
    return {"ok": True}
