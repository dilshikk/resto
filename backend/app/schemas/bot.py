from pydantic import BaseModel

from app.schemas.checklist import ChecklistOut, CurrentItemOut


class BotLinkRequest(BaseModel):
    telegram_id: int
    invite_code: str


class BotEmployeeOut(BaseModel):
    id: int
    full_name: str
    role_name: str
    role_level: int
    primary_branch_name: str
    status: str
    # Preferred language for Telegram bot messages: "ru" | "uz" | "en"
    preferred_language: str = "ru"


class BotToggleRequest(BaseModel):
    telegram_id: int
    note: str | None = None


class BotSkipRequest(BaseModel):
    telegram_id: int
    note: str | None = None


# Re-exported for convenience so bot router callers only need this module
__all__ = [
    "BotLinkRequest",
    "BotEmployeeOut",
    "BotToggleRequest",
    "BotSkipRequest",
    "ChecklistOut",
    "CurrentItemOut",
]
