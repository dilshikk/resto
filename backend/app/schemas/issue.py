from datetime import datetime
from pydantic import BaseModel


class IssueCreate(BaseModel):
    title: str
    description: str | None = None
    branch_id: int
    category: str = "general"
    priority: str = "medium"
    photo_urls: list[str] = []
    checklist_id: int | None = None


class IssueCommentCreate(BaseModel):
    text: str


class IssueCommentOut(BaseModel):
    id: int
    issue_id: int
    author_name: str
    text: str
    created_at: datetime


class IssueOut(BaseModel):
    id: int
    title: str
    description: str | None
    branch_id: int
    branch_name: str
    category: str
    priority: str
    status: str
    photo_urls: list[str]
    reported_by_name: str
    assigned_to_name: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    comment_count: int


class IssueDetail(IssueOut):
    comments: list[IssueCommentOut]


class IssueStatusUpdate(BaseModel):
    status: str  # open | in_progress | closed
    assigned_to_employee_id: int | None = None
