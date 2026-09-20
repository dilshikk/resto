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


class BotLinkResponse(BotEmployeeOut):
    """Returned by POST /bot/link.

    The bot MUST persist `bot_session_token` for this telegram_id and include
    it as `X-Bot-Employee-Token` on every subsequent per-employee request.
    The token is shown here exactly once — the backend only stores its hash.
    """
    bot_session_token: str


class BotToggleRequest(BaseModel):
    note: str | None = None


class BotSkipRequest(BaseModel):
    note: str | None = None


# Re-exported for convenience so bot router callers only need this module
__all__ = [
    "BotLinkRequest",
    "BotLinkResponse",
    "BotEmployeeOut",
    "BotToggleRequest",
    "BotSkipRequest",
    "ChecklistOut",
    "CurrentItemOut",
]
