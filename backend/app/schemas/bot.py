from pydantic import BaseModel

from app.schemas.checklist import ChecklistOut, CurrentItemOut


class BotLinkRequest(BaseModel):
    telegram_id: int
    invite_code: str


class BotResyncRequest(BaseModel):
    """
    Body for POST /bot/resync — recovers a lost bot session token for a
    telegram_id that is already linked to an employee, without requiring
    the invite code again. See routers/bot.py for the full rationale.
    """
    telegram_id: int


class BotRegisterRequest(BaseModel):
    """
    Body for POST /bot/register — self-service registration triggered by
    /start when the telegram_id has never been seen before. Creates a new
    employee record with status="pending" and no role/branch; a manager
    assigns those on confirmation (see EmployeeApprove).
    """
    telegram_id: int
    full_name: str
    username: str | None = None
    phone: str | None = None


class BotStatusOut(BaseModel):
    """
    Response for GET /bot/status — lets the bot decide what to show on
    /start without needing a per-employee token yet (a "pending" or
    "blocked" employee never has one).
    """
    status: str  # not_registered | pending | active | blocked | archived | inactive | fired
    full_name: str | None = None
    role_name: str | None = None
    primary_branch_name: str | None = None
    preferred_language: str = "ru"


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
    """Returned by POST /bot/link and POST /bot/resync.

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
    "BotResyncRequest",
    "BotRegisterRequest",
    "BotStatusOut",
    "BotLinkResponse",
    "BotEmployeeOut",
    "BotToggleRequest",
    "BotSkipRequest",
    "ChecklistOut",
    "CurrentItemOut",
]
