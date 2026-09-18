from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ShiftCreate(BaseModel):
    employee_id: int
    branch_id: int
    shift_date: str  # YYYY-MM-DD
    starts_at: str  # HH:MM
    ends_at: str  # HH:MM


class ShiftUpdate(BaseModel):
    starts_at: str | None = None
    ends_at: str | None = None
    status: str | None = None  # planned | active | completed | no_show


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    employee_name: str
    branch_id: int
    branch_name: str
    shift_date: str
    starts_at: str
    ends_at: str
    status: str
    created_at: datetime
    updated_at: datetime
