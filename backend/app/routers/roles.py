from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import require_manager
from app.database import get_db
from app.models.employee import Employee
from app.models.role import Role
from app.schemas.role import RoleOut

router = APIRouter(prefix="/roles", tags=["roles"])

DEFAULT_ROLES = [
    {"code": "waiter", "name_ru": "Официант", "category": "staff", "permission_level": 0},
    {"code": "runner", "name_ru": "Раннер", "category": "staff", "permission_level": 0},
    {"code": "hostess", "name_ru": "Хостес", "category": "staff", "permission_level": 0},
    {"code": "bartender", "name_ru": "Бармен", "category": "staff", "permission_level": 0},
    {"code": "cashier", "name_ru": "Кассир", "category": "staff", "permission_level": 0},
    {"code": "cook", "name_ru": "Повар", "category": "staff", "permission_level": 0},
    {"code": "confectioner", "name_ru": "Кондитер", "category": "staff", "permission_level": 0},
    {"code": "cleaner", "name_ru": "Уборщик", "category": "staff", "permission_level": 0},
    {"code": "manager", "name_ru": "Менеджер", "category": "management", "permission_level": 1},
    {"code": "senior_manager", "name_ru": "Старший менеджер", "category": "management", "permission_level": 1},
    {"code": "supervisor", "name_ru": "Управляющий", "category": "management", "permission_level": 2},
    {"code": "director", "name_ru": "Директор", "category": "management", "permission_level": 3},
]


@router.get("", response_model=list[RoleOut])
async def list_roles(
    _: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role))
    return result.scalars().all()


@router.post("/seed", include_in_schema=False)
async def seed_roles(db: AsyncSession = Depends(get_db)):
    """Заполняет таблицу roles стандартными должностями MADO (идемпотентно)."""
    for role_data in DEFAULT_ROLES:
        existing = await db.execute(select(Role).where(Role.code == role_data["code"]))
        if not existing.scalar_one_or_none():
            db.add(Role(**role_data))
    await db.commit()
    return {"ok": True}
