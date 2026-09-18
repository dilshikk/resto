from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BranchBase(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    timezone: str = "Asia/Tashkent"


class BranchCreate(BranchBase):
    pass


class BranchOut(BranchBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
