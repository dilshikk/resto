import datetime as dt

from pydantic import BaseModel, Field


class ScheduleBase(BaseModel):
    template_id: int
    shift: str = "morning"
    start_date: dt.date
    end_date: dt.date | None = None
    # ISO weekdays 1 (Mon) .. 7 (Sun)
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    window_start: dt.time
    window_end: dt.time


class ScheduleCreate(ScheduleBase):
    # One schedule is created per selected branch.
    branch_ids: list[int]


class ScheduleUpdate(ScheduleBase):
    branch_id: int
    is_active: bool = True


class ScheduleOut(ScheduleBase):
    id: int
    branch_id: int
    branch_name: str
    template_name: str
    is_active: bool
    created_at: dt.datetime
