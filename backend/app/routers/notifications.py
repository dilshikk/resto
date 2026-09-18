from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_user
from app.database import get_db
from app.models.employee import Employee
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def notify(db: AsyncSession, employee_id: int, type_: str, title: str, message: str | None = None) -> None:
    """Создаёт уведомление сотруднику. Вызывается из других роутеров (например, issues)."""
    db.add(Notification(recipient_employee_id=employee_id, type=type_, title=title, message=message))


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).where(Notification.recipient_employee_id == current.id)
    if unread_only:
        q = q.where(Notification.is_read == False)
    q = q.order_by(Notification.created_at.desc()).limit(50)
    return (await db.execute(q)).scalars().all()


@router.get("/unread-count")
async def unread_count(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(func.count()).select_from(Notification).where(
        Notification.recipient_employee_id == current.id,
        Notification.is_read == False,
    )
    count = (await db.execute(q)).scalar_one()
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = (await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )).scalar_one_or_none()
    if not notif or notif.recipient_employee_id != current.id:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    notif.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).where(
        Notification.recipient_employee_id == current.id,
        Notification.is_read == False,
    )
    unread = (await db.execute(q)).scalars().all()
    for n in unread:
        n.is_read = True
    await db.commit()
    return {"ok": True, "updated": len(unread)}
