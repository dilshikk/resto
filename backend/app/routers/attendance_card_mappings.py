"""
Сопоставление зашифрованных ID карт терминала (хеш в employeeNoString при
проходе по карте) с обычным faceid_employee_id. Используется JSON-импортом
(attendance_import.py), чтобы такие события подставляли нужного сотрудника
вместо того, чтобы пропускаться.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_manager
from app.database import get_db
from app.models.attendance_card_mapping import AttendanceCardMapping
from app.models.employee import Employee

router = APIRouter(prefix="/attendance-card-mappings", tags=["attendance"])

MAX_HASH_LENGTH = 128


class MappingOut(BaseModel):
    hashed_id: str
    faceid_employee_id: str
    note: str | None = None


class MappingUpsert(BaseModel):
    faceid_employee_id: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=255)


@router.get("", response_model=list[MappingOut])
async def list_mappings(
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Все сохранённые привязки хеш -> сотрудник."""
    rows = (await db.execute(select(AttendanceCardMapping))).scalars().all()
    return [
        MappingOut(hashed_id=r.hashed_id, faceid_employee_id=r.faceid_employee_id, note=r.note)
        for r in rows
    ]


@router.put("/{hashed_id}", response_model=MappingOut)
async def upsert_mapping(
    hashed_id: str,
    body: MappingUpsert,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт или обновляет привязку. После сохранения повторный импорт того же
    JSON подставит указанного сотрудника вместо пропуска события."""
    if len(hashed_id) > MAX_HASH_LENGTH:
        raise HTTPException(status_code=422, detail="Хеш слишком длинный")

    row = (
        await db.execute(select(AttendanceCardMapping).where(AttendanceCardMapping.hashed_id == hashed_id))
    ).scalar_one_or_none()
    if row is None:
        row = AttendanceCardMapping(
            hashed_id=hashed_id, faceid_employee_id=body.faceid_employee_id, note=body.note
        )
        db.add(row)
    else:
        row.faceid_employee_id = body.faceid_employee_id
        row.note = body.note

    await db.commit()
    await db.refresh(row)
    return MappingOut(hashed_id=row.hashed_id, faceid_employee_id=row.faceid_employee_id, note=row.note)


@router.delete("/{hashed_id}")
async def delete_mapping(
    hashed_id: str,
    _current: Employee = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(AttendanceCardMapping).where(AttendanceCardMapping.hashed_id == hashed_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Привязка не найдена")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
