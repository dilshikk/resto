from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import require_manager
from app.database import get_db
from app.models.employee import Employee
from app.models.role import Role
from app.schemas.role import RoleOut

router = APIRouter(prefix="/roles", tags=["roles"])

# can_access_all_branches is True for supervisor and director: these roles
# need visibility across every branch.  Manager-level roles are scoped to
# their assigned branches only.  Set explicitly here so the meaning of the
# flag is obvious and changing permission_level in the future does not
# silently affect branch visibility.
DEFAULT_ROLES = [
    {"code": "waiter",         "name_ru": "\u041e\u0444\u0438\u0446\u0438\u0430\u043d\u0442",         "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "runner",         "name_ru": "\u0420\u0430\u043d\u043d\u0435\u0440",           "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "hostess",        "name_ru": "\u0425\u043e\u0441\u0442\u0435\u0441",           "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "bartender",      "name_ru": "\u0411\u0430\u0440\u043c\u0435\u043d",            "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "cashier",        "name_ru": "\u041a\u0430\u0441\u0441\u0438\u0440",            "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "cook",           "name_ru": "\u041f\u043e\u0432\u0430\u0440",             "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "confectioner",   "name_ru": "\u041a\u043e\u043d\u0434\u0438\u0442\u0435\u0440",         "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "cleaner",        "name_ru": "\u0423\u0431\u043e\u0440\u0449\u0438\u043a",           "category": "staff",       "permission_level": 0, "can_access_all_branches": False},
    {"code": "manager",        "name_ru": "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440",          "category": "management",  "permission_level": 1, "can_access_all_branches": False},
    {"code": "senior_manager", "name_ru": "\u0421\u0442\u0430\u0440\u0448\u0438\u0439 \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440",   "category": "management",  "permission_level": 1, "can_access_all_branches": False},
    {"code": "supervisor",     "name_ru": "\u0423\u043f\u0440\u0430\u0432\u043b\u044f\u044e\u0449\u0438\u0439",        "category": "management",  "permission_level": 2, "can_access_all_branches": True},
    {"code": "director",       "name_ru": "\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440",          "category": "management",  "permission_level": 3, "can_access_all_branches": True},
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
    """Заполняет таблицу roles стандартными должностями MADO (идемпотентно).

    For existing rows the can_access_all_branches column is also updated so
    that a re-seed after the schema migration brings old rows into sync.
    """
    for role_data in DEFAULT_ROLES:
        existing = (await db.execute(select(Role).where(Role.code == role_data["code"]))).scalar_one_or_none()
        if existing:
            # Keep name and levels in sync; update the new flag on existing rows.
            existing.can_access_all_branches = role_data["can_access_all_branches"]
        else:
            db.add(Role(**role_data))
    await db.commit()
    return {"ok": True}
