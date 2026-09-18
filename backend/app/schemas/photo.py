from datetime import datetime
from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: int
    checklist_item_id: int
    url: str
    uploaded_by_name: str
    created_at: datetime
