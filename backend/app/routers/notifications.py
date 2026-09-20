"""
REST + WebSocket API for employee notifications.

REST endpoints (all require Bearer token)
─────────────────────────────────────────
  GET  /notifications              – list last 50, optional ?unread_only=true
  GET  /notifications/unread-count – { count: N }
  POST /notifications/{id}/read    – mark one as read
  POST /notifications/read-all     – mark all as read

WebSocket endpoint
──────────────────
  WS  /notifications/ws?token={access_token}

  The token is passed as a query parameter because browser WebSocket clients
  cannot set Authorization headers.  The endpoint validates it the same way
  HTTP endpoints do (JWT → revocation check → Employee lookup).

  After a successful handshake the server:
    • Sends a "connected" frame so the client knows the pipe is open.
    • Keeps the connection alive by consuming incoming frames (clients should
      send periodic {"type":"ping"} messages; anything else is ignored).
    • Automatically removes the connection on disconnect / error.

  Server → client frames use this envelope:
    {
      "event": "notification",          // always "notification" for now
      "id": <int>,
      "type": "<reminder|overdue|…>",
      "title": "<string>",
      "message": "<string|null>",
      "is_read": false,
      "created_at": "<ISO-8601 UTC>"
    }

Helper (used by other routers)
───────────────────────────────
  await notify(db, employee_id, type_, title, message)

  Creates a DB row *and* immediately pushes the payload via WebSocket to
  every active browser session of that employee (fire-and-forget: if the
  employee has no open socket the notification is still persisted in DB).
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth import get_current_user, is_token_revoked
from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.models.employee import Employee, EmployeeAccount
from app.models.notification import Notification
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── WebSocket auth helper ─────────────────────────────────────────────────────

async def _resolve_employee_from_token(token: str, db: AsyncSession) -> Employee | None:
    """
    Validate an access token (same rules as get_current_user) and return the
    linked Employee, or None if anything is invalid / the account is not linked.

    Never raises — callers use the None return to close the socket cleanly.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    if payload.get("type") != "access" or not payload.get("sub"):
        return None

    jti = payload.get("jti")
    if jti and await is_token_revoked(jti, db):
        return None

    user = (
        await db.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if not user:
        return None

    account = (
        await db.execute(
            select(EmployeeAccount).where(EmployeeAccount.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not account:
        return None

    employee = (
        await db.execute(
            select(Employee).where(Employee.id == account.employee_id)
        )
    ).scalar_one_or_none()

    if not employee or employee.status == "fired":
        return None

    return employee


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    token: str = Query(..., description="Access token — передаётся как query-параметр, т.к. браузер не поддерживает заголовки при WS"),
):
    """
    Real-time notification channel for a single authenticated employee.

    Authentication: `?token=<access_jwt>` (same JWT as Bearer auth).

    Client → server frames:
      { "type": "ping" }  — keepalive (server ignores, connection stays open)

    Server → client frames:
      { "event": "connected", "employee_id": <int> }
      { "event": "notification", "id": …, "type": …, "title": …,
        "message": …, "is_read": false, "created_at": "…" }
    """
    # Open a dedicated DB session for this long-lived connection.
    async with AsyncSessionLocal() as db:
        employee = await _resolve_employee_from_token(token, db)

    if employee is None:
        # Reject before accepting — sends HTTP 403 back to the client.
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await ws_manager.connect(employee.id, websocket)
    logger.info("WS connected: employee_id=%d (total=%d)", employee.id, ws_manager.active_count)

    try:
        # Confirm the handshake to the client.
        await websocket.send_json({"event": "connected", "employee_id": employee.id})

        # Keep the connection alive; handle incoming frames (ping/pong, etc.)
        while True:
            raw = await websocket.receive_text()
            try:
                frame = json.loads(raw)
            except (ValueError, TypeError):
                frame = {}

            # Only "ping" is meaningful from the client right now.
            if frame.get("type") == "ping":
                await websocket.send_json({"event": "pong"})
            # All other frames are silently ignored.

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS error for employee_id=%d: %s", employee.id, exc)
    finally:
        await ws_manager.disconnect(employee.id, websocket)
        logger.info(
            "WS disconnected: employee_id=%d (total=%d)", employee.id, ws_manager.active_count
        )


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).where(Notification.recipient_employee_id == current.id)
    if unread_only:
        q = q.where(Notification.is_read == False)  # noqa: E712
    q = q.order_by(Notification.created_at.desc()).limit(50)
    return (await db.execute(q)).scalars().all()


@router.get("/unread-count")
async def unread_count(
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(func.count()).select_from(Notification).where(
        Notification.recipient_employee_id == current.id,
        Notification.is_read == False,  # noqa: E712
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
        Notification.is_read == False,  # noqa: E712
    )
    unread = (await db.execute(q)).scalars().all()
    for n in unread:
        n.is_read = True
    await db.commit()
    return {"ok": True, "updated": len(unread)}


# ── Shared helper (imported by other routers) ─────────────────────────────────

async def notify(
    db: AsyncSession,
    employee_id: int,
    type_: str,
    title: str,
    message: str | None = None,
) -> None:
    """
    Persist a notification row in the DB *and* push it via WebSocket.

    Designed to be awaited inside any mutation that needs to alert an employee
    (e.g. issue assigned, checklist overdue, escalation triggered).

    The WebSocket push is fire-and-forget: if the employee has no active
    connection, the push is simply skipped — the notification is still
    persisted and the employee will see it next time they poll or reload.

    Example
    -------
    await notify(db, employee_id=manager.id, type_="issue_assigned",
                 title="Новая проблема", message="Сломан кофемашина #3")
    """
    # 1. Persist to DB (caller is responsible for commit).
    notif = Notification(
        recipient_employee_id=employee_id,
        type=type_,
        title=title,
        message=message,
    )
    db.add(notif)
    await db.flush()  # populate notif.id and notif.created_at

    # 2. Push to any open WebSocket connections for this employee.
    if ws_manager.is_connected(employee_id):
        payload = {
            "event": "notification",
            "id": notif.id,
            "type": notif.type,
            "title": notif.title,
            "message": notif.message,
            "is_read": False,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        }
        # Use a background task so the DB flush/commit path is never delayed
        # by potentially slow WebSocket I/O (large fan-out, slow clients, etc.)
        import asyncio
        asyncio.ensure_future(ws_manager.send(employee_id, payload))
