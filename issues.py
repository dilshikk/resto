from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class IssueStatus(str, Enum):
    new = "new"
    in_progress = "in_progress"
    resolved = "resolved"


class IssueCreate(BaseModel):
    task_result_id: Optional[int] = None
    branch_id: int
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_at: Optional[datetime] = None


class IssueUpdate(BaseModel):
    status: Optional[IssueStatus] = None
    assigned_to: Optional[int] = None
    due_at: Optional[datetime] = None
    description: Optional[str] = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_result_id: Optional[int] = None
    branch_id: int
    reported_by: int
    title: str
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_at: Optional[datetime] = None
    status: IssueStatus
    created_at: datetime
    updated_at: datetime


class IssueCommentCreate(BaseModel):
    comment: str = Field(..., min_length=1)


class IssueCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    author_id: int
    comment: str
    created_at: datetime
