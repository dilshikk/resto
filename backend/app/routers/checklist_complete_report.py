"""
Wraps the web-panel POST /checklists/{id}/complete so a PDF report is sent
to the managers' group after a successful completion.

This router is included in main.py BEFORE checklists.router, so FastAPI
matches it first; the original completion logic is reused unchanged.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.checklist_report import schedule_checklist_report
from app.database import get_db
from app.models.employee import Employee
from app.routers import checklists

router = APIRouter(prefix="/checklists", tags=["checklists"])


@router.post("/{checklist_id}/complete")
async def complete_checklist_with_report(
    checklist_id: int,
    current: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await checklists.complete_checklist(checklist_id=checklist_id, current=current, db=db)
    schedule_checklist_report(checklist_id, current.full_name)
    return result
