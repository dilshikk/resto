from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import get_current_user, require_supervisor
from app.database import get_db
from app.models.employee import Employee
from app.models.standard import Standard
from app.schemas.standard import StandardCreate, StandardUpdate, StandardOut

router = APIRouter(prefix="/standards", tags=["standards"])


@router.get("", response_model=list[StandardOut])
async def list_standards(
    category: str | None = None,
    include_inactive: bool = False,
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Standard)
    if category:
        q = q.where(Standard.category == category)
    if not include_inactive:
        q = q.where(Standard.is_active == True)  # noqa: E712
    q = q.order_by(Standard.category, Standard.code)
    return (await db.execute(q)).scalars().all()


@router.get("/{code}", response_model=StandardOut)
async def get_standard(
    code: str,
    _: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    standard = (await db.execute(select(Standard).where(Standard.code == code))).scalar_one_or_none()
    if not standard:
        raise HTTPException(status_code=404, detail="Стандарт не найден")
    return standard


@router.post("", response_model=StandardOut)
async def create_standard(
    data: StandardCreate,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    code = data.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Код стандарта обязателен")
    existing = (await db.execute(select(Standard).where(Standard.code == code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Стандарт с таким кодом уже существует")

    standard = Standard(
        code=code,
        category=data.category,
        title=data.title.strip(),
        description=data.description,
    )
    db.add(standard)
    await db.commit()
    await db.refresh(standard)
    return standard


@router.patch("/{code}", response_model=StandardOut)
async def update_standard(
    code: str,
    data: StandardUpdate,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    standard = (await db.execute(select(Standard).where(Standard.code == code))).scalar_one_or_none()
    if not standard:
        raise HTTPException(status_code=404, detail="Стандарт не найден")

    if data.category is not None:
        standard.category = data.category
    if data.title is not None:
        standard.title = data.title.strip()
    if data.description is not None:
        standard.description = data.description
    if data.is_active is not None:
        standard.is_active = data.is_active

    await db.commit()
    await db.refresh(standard)
    return standard
