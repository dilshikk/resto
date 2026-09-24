from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EmployeeCreate(BaseModel):
    full_name: str
    phone: str | None = None
    role_id: int
    primary_branch_id: int
    additional_branch_ids: list[int] = []
    hired_at: str | None = None
    preferred_language: str = "ru"


class EmployeeUpdate(BaseModel):
    """
    True partial-update schema: every field is Optional so the client only
    has to send the fields it wants to change.  The router applies only the
    fields present in model_fields_set, leaving everything else untouched.
    """
    full_name: str | None = None
    phone: str | None = None
    role_id: int | None = None
    primary_branch_id: int | None = None
    additional_branch_ids: list[int] | None = None
    status: str | None = None
    hired_at: str | None = None
    preferred_language: str | None = None


class EmployeeApprove(BaseModel):
    """
    Body for POST /employees/{id}/approve — turns a self-registered
    ("pending") employee into an active one by assigning the restaurant
    (branch) and position (role) a manager picks in the "Сотрудники" screen.
    """
    role_id: int
    primary_branch_id: int
    additional_branch_ids: list[int] = []
    hired_at: str | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None = None
    # Optional: a self-registered employee has no role/branch until a
    # manager approves the request (see EmployeeApprove).
    role_id: int | None = None
    role_name: str | None = None
    role_level: int = 0
    primary_branch_id: int | None = None
    primary_branch_name: str | None = None
    additional_branch_ids: list[int]
    status: str
    invite_code: str | None = None
    has_claimed_account: bool
    telegram_linked: bool
    telegram_username: str | None = None
    hired_at: str | None = None
    preferred_language: str = "ru"
    last_activity_at: str | None = None
    created_at: datetime
    updated_at: datetime


class MyProfile(BaseModel):
    id: int
    full_name: str
    status: str
    role_id: int
    role_name: str
    role_code: str
    role_level: int
    primary_branch_id: int
    primary_branch_name: str
    additional_branch_ids: list[int]
    preferred_language: str = "ru"


class BootstrapRequest(BaseModel):
    full_name: str
    branch_name: str
    timezone: str = "Asia/Tashkent"


class ClaimRequest(BaseModel):
    invite_code: str
