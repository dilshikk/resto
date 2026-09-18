from datetime import datetime
from pydantic import BaseModel, ConfigDict


CATEGORIES = [
    "service", "cleanliness", "uniform", "kitchen", "bar",
    "cashier", "warehouse", "grill", "delivery", "safety",
]


class StandardCreate(BaseModel):
    code: str
    category: str
    title: str
    description: str | None = None


class StandardUpdate(BaseModel):
    category: str | None = None
    title: str | None = None
    description: str | None = None
    is_active: bool | None = None


class StandardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    category: str
    title: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
