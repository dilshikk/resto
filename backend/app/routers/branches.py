from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_supervisor
from app.database import get_db
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.role import Role
from app.schemas.branch import BranchCreate, BranchOut

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchOut])
async def list_branches(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role_result = await db.execute(select(Role).where(Role.id == current.role_id))
    role = role_result.scalar_one_or_none()

    result = await db.execute(select(Branch).where(Branch.is_active == True))
    branches = result.scalars().all()

    if role and role.permission_level >= 2:
        return branches

    allowed = {current.primary_branch_id, *current.additional_branch_ids}
    return [b for b in branches if b.id in allowed]


@router.post("", response_model=BranchOut)
async def create_branch(
    data: BranchCreate,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Название филиала обязательно")
    branch = Branch(**data.model_dump())
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.patch("/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: int,
    data: BranchCreate,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал не найден")

    for k, v in data.model_dump(exclude_none=True).items():
        setattr(branch, k, v)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.delete("/{branch_id}")
async def deactivate_branch(
    branch_id: int,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал не найден")
    branch.is_active = False
    await db.commit()
    return {"ok": True}
