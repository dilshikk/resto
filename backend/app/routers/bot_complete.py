"""
POST /bot/checklists/{id}/complete — lets the Telegram bot close a checklist
once the employee has gone through every item. Previously the bot flow ended
without marking the checklist completed, so no report could be triggered.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_bot_secret
from app.checklist_report import schedule_checklist_report
from app.database import get_db
from app.models.checklist import Checklist
from app.models.employee import Employee
from app.routers.audit_logs import log_action
from app.routers.bot import get_employee_by_bot_token
from app.routers.checklists import _compute_deadline_status, _get_ordered_items, _is_item_pending

router = APIRouter(prefix="/bot", tags=["bot"], dependencies=[Depends(verify_bot_secret)])


@router.post("/checklists/{checklist_id}/complete")
async def complete_my_checklist(
    checklist_id: int,
    emp: Employee = Depends(get_employee_by_bot_token),
    db: AsyncSession = Depends(get_db),
):
    cl = (await db.execute(select(Checklist).where(Checklist.id == checklist_id))).scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=404, detail="Чек-лист не найден")
    if cl.status == "completed":
        # Idempotent: the bot may call this again when reopening a finished checklist.
        return {"ok": True, "already_completed": True, "deadline_status": _compute_deadline_status(cl)}

    allowed = {emp.primary_branch_id, *(emp.additional_branch_ids or [])}
    if cl.branch_id not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к чек-листу другого филиала")

    items = await _get_ordered_items(checklist_id, db)
    pending_required = [i for i in items if i.is_required and _is_item_pending(i)]
    if pending_required:
        titles = ", ".join(f"«{i.title}»" for i in pending_required[:3])
        raise HTTPException(status_code=400, detail=f"Нельзя завершить: не выполнены обязательные пункты: {titles}")

    now = datetime.now(timezone.utc)
    cl.status = "completed"
    cl.completed_at = now
    emp.last_activity_at = now

    await log_action(
        db,
        actor_id=emp.id,
        action="checklist.completed",
        entity_type="checklist",
        entity_id=cl.id,
        metadata={
            "completed_at": now.isoformat(),
            "deadline_status": _compute_deadline_status(cl),
            "via": "telegram",
        },
    )
    await db.commit()
    schedule_checklist_report(cl.id, emp.full_name)
    return {"ok": True, "already_completed": False, "deadline_status": _compute_deadline_status(cl)}
