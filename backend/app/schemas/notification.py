from datetime import datetime
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    message: str | None
    is_read: bool
    created_at: datetime
