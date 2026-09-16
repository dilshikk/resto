from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Language(str, Enum):
    ru = "ru"
    uz = "uz"
    en = "en"
    tr = "tr"


class EmployeeStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    fired = "fired"


class EmployeeBase(BaseModel):
    full_name: str = Field(..., max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    role_id: int
    preferred_language: Language = Language.ru


class EmployeeCreate(EmployeeBase):
    telegram_id: Optional[int] = None
    hired_at: Optional[date] = None
    branch_ids: list[int] = Field(default_factory=list, description="Филиалы, к которым привязан сотрудник")


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    role_id: Optional[int] = None
    preferred_language: Optional[Language] = None
    status: Optional[EmployeeStatus] = None
    branch_ids: Optional[list[int]] = None


class EmployeeOut(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: Optional[int] = None
    status: EmployeeStatus
    hired_at: Optional[date] = None
    branch_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EmployeePerformanceOut(BaseModel):
    employee_id: int
    period_start: date
    period_end: date
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    problem_tasks: int
    completion_rate: float = Field(..., description="Процент выполнения, 0-100")
