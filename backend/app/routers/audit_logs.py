from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth import require_supervisor, get_current_user
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.employee import Employee
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


async def log_action(
    db: AsyncSession,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Записывает действие в неизменяемый журнал аудита. Вызывается из других роутеров.

    Не коммитит сессию — запись войдёт в ту же транзакцию, что и основное изменение.
    """
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        )
    )


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    _: Employee = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
):
    """Журнал действий. Доступен управляющему и директору (раздел 3.2 ТЗ)."""
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        q = q.where(AuditLog.actor_id == actor_id)
    if date_from:
        q = q.where(AuditLog.created_at >= date_from)
    if date_to:
        q = q.where(AuditLog.created_at <= date_to)
    q = q.order_by(AuditLog.created_at.desc()).limit(min(limit, 500))

    logs = (await db.execute(q)).scalars().all()

    outs = []
    for log in logs:
        actor_name = None
        if log.actor_id:
            emp = (await db.execute(select(Employee).where(Employee.id == log.actor_id))).scalar_one_or_none()
            actor_name = emp.full_name if emp else None
        outs.append(
            AuditLogOut(
                id=log.id,
                actor_id=log.actor_id,
                actor_name=actor_name,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                metadata=log.metadata_,
                created_at=log.created_at,
            )
        )
    return outs


@router.get("/my", response_model=list[AuditLogOut])
async def my_recent_actions(
    limit: int = 50,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Собственная история действий сотрудника (без прав супервайзера)."""
    q = (
        select(AuditLog)
        .where(AuditLog.actor_id == current.id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 200))
    )
    logs = (await db.execute(q)).scalars().all()
    return [
        AuditLogOut(
            id=log.id,
            actor_id=log.actor_id,
            actor_name=current.full_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            metadata=log.metadata_,
            created_at=log.created_at,
        )
        for log in logs
    ]
