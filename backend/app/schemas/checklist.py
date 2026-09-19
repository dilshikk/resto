from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ── Template schemas ────────────────────────────────────────────────────────

class TemplateItemCreate(BaseModel):
    title: str
    description: str | None = None
    sort_order: int = 0
    is_required: bool = True
    standard_code: str | None = None


class TemplateItemOut(TemplateItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    template_id: int


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    category: str = "general"
    branch_id: int | None = None
    # Minutes after checklist creation until the deadline is due.
    # None means this template has no deadline.
    deadline_offset_minutes: int | None = None


class TemplateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    category: str
    branch_id: int | None = None
    branch_name: str | None = None
    is_active: bool
    item_count: int
    deadline_offset_minutes: int | None = None
    created_at: datetime


class TemplateDetail(TemplateListItem):
    items: list[TemplateItemOut]


# ── Checklist schemas ────────────────────────────────────────────────────────

class ChecklistCreate(BaseModel):
    template_id: int
    branch_id: int
    shift: str = "morning"
    date: str  # YYYY-MM-DD


class ChecklistItemPhotoOut(BaseModel):
    id: int
    url: str
    uploaded_by_name: str
    created_at: datetime


class ChecklistItemOut(BaseModel):
    id: int
    checklist_id: int
    title: str
    description: str | None = None
    is_required: bool
    sort_order: int
    is_completed: bool
    is_skipped: bool
    completed_by_name: str | None = None
    completed_at: datetime | None = None
    note: str | None = None
    photos: list[ChecklistItemPhotoOut] = []
    standard_code: str | None = None
    standard_title: str | None = None


class ChecklistOut(BaseModel):
    id: int
    template_id: int
    template_name: str
    branch_id: int
    branch_name: str
    shift: str
    date: str
    status: str
    total_items: int
    completed_items: int
    skipped_items: int
    created_at: datetime
    # Deadline tracking (None for legacy checklists without deadline data)
    started_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    # Computed status: ON_TIME | OVERDUE | NOT_COMPLETED | None
    deadline_status: str | None = None


class ChecklistDetail(ChecklistOut):
    items: list[ChecklistItemOut]


class ToggleItemRequest(BaseModel):
    note: str | None = None


class SkipItemRequest(BaseModel):
    note: str | None = None


# Returned by GET /checklists/{id}/current-item
# None means all items are done/skipped → checklist can be completed
class CurrentItemOut(BaseModel):
    id: int
    checklist_id: int
    title: str
    description: str | None = None
    is_required: bool
    sort_order: int
    total_items: int
    current_position: int  # 1-based index among all items
    standard_code: str | None = None
    standard_title: str | None = None
