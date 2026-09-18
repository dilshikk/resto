from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EmployeeCreate(BaseModel):
    full_name: str
    phone: str | None = None
    role_id: int
    primary_branch_id: int
    additional_branch_ids: list[int] = []
    hired_at: str | None = None


class EmployeeUpdate(EmployeeCreate):
    status: str = "active"


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    phone: str | None = None
    role_id: int
    role_name: str
    role_level: int
    primary_branch_id: int
    primary_branch_name: str
    additional_branch_ids: list[int]
    status: str
    invite_code: str
    has_claimed_account: bool
    hired_at: str | None = None
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


class BootstrapRequest(BaseModel):
    full_name: str
    branch_name: str
    timezone: str = "Asia/Tashkent"


class ClaimRequest(BaseModel):
    invite_code: str
