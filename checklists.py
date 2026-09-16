from datetime import datetime, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class Stage(str, Enum):
    opening = "opening"
    during_shift = "during_shift"
    closing = "closing"


class TaskType(str, Enum):
    checkbox = "checkbox"
    number = "number"
    temperature = "temperature"
    text = "text"
    photo = "photo"
    photo_geo = "photo_geo"
    yes_no = "yes_no"


class ChecklistTaskBase(BaseModel):
    title_ru: str = Field(..., max_length=255)
    title_uz: Optional[str] = Field(None, max_length=255)
    title_en: Optional[str] = Field(None, max_length=255)
    title_tr: Optional[str] = Field(None, max_length=255)
    task_type: TaskType
    is_required: bool = True
    requires_photo: bool = False
    requires_comment_on_negative: bool = False
    standard_code: Optional[str] = Field(None, max_length=30)
    sort_order: int = 0
    due_offset_minutes: Optional[int] = None


class ChecklistTaskCreate(ChecklistTaskBase):
    section_id: Optional[int] = None


class ChecklistTaskOut(ChecklistTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    section_id: Optional[int] = None


class ChecklistTemplateBase(BaseModel):
    name: str = Field(..., max_length=150)
    role_id: int
    stage: Stage
    branch_id: Optional[int] = Field(None, description="NULL = общий шаблон для всех филиалов")
    starts_at: time
    deadline_at: time

    @model_validator(mode="after")
    def check_time_order(self):
        if self.deadline_at <= self.starts_at:
            raise ValueError("deadline_at должен быть позже starts_at")
        return self


class ChecklistTemplateCreate(ChecklistTemplateBase):
    pass


class ChecklistTemplateOut(ChecklistTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    tasks: list[ChecklistTaskOut] = Field(default_factory=list)


class TaskReorderItem(BaseModel):
    task_id: int
    sort_order: int


class TaskReorderRequest(BaseModel):
    items: list[TaskReorderItem]
