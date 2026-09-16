from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class AssignmentStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"


class TaskResultStatus(str, Enum):
    done = "done"
    problem = "problem"
    not_relevant = "not_relevant"
    pending = "pending"


class ChecklistAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    employee_id: int
    branch_id: int
    shift_id: Optional[int] = None
    assignment_date: date
    status: AssignmentStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = Field(0, description="Вычисляется на бэкенде: done / total * 100")


class TaskResultIn(BaseModel):
    """Тело запроса при фиксации ответа сотрудника по задаче."""
    value: Any = Field(..., description="Значение ответа: bool, число, строка, или объект {answer: 'no'}")
    status: TaskResultStatus
    comment: Optional[str] = Field(None, description="Обязателен, если status=problem и requires_comment_on_negative=true")


class PhotoIn(BaseModel):
    file_url: str = Field(..., max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PhotoOut(PhotoIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_result_id: int
    uploaded_at: datetime


class TaskResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    task_id: int
    value: Any
    status: TaskResultStatus
    completed_at: Optional[datetime] = None
    is_overdue: bool
    completed_by: Optional[int] = None
    photos: list[PhotoOut] = Field(default_factory=list)


class GenerateAssignmentsRequest(BaseModel):
    target_date: date
    branch_id: Optional[int] = Field(None, description="Если не указан — генерация по всем филиалам")
