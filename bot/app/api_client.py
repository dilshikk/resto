"""Thin async client for the backend's /api/v1/bot/* endpoints.

Authentication model
--------------------
Every request carries two credentials:
  X-Bot-Secret            -- proves the request comes from *our* bot service
  X-Bot-Employee-Token    -- per-employee token issued by POST /bot/link
                             (required on all endpoints except /bot/link itself)

The plaintext token is stored in-memory keyed by telegram_id.  On bot
restart the cache is empty; the first command that needs an employee token
calls _ensure_token() which raises ApiError(401) if the employee hasn't
linked yet (asking them to /start again).
"""
from typing import Any

import httpx

from app.config import BACKEND_URL, BOT_INTERNAL_SECRET

# Base headers sent on every request (bot-level authentication).
_BASE_HEADERS = {"X-Bot-Secret": BOT_INTERNAL_SECRET}

# In-memory caches keyed by telegram_id.
# Both are populated when an employee links their account or on first
# successful /bot/me call.  Both are lost on bot restart.
_lang_cache: dict[int, str] = {}           # telegram_id -> "ru"|"uz"|"en"
_token_cache: dict[int, str] = {}          # telegram_id -> bot_session_token


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ---- Cache helpers -----------------------------------------------------------

def set_lang_cache(telegram_id: int, lang: str) -> None:
    """Explicitly cache a user's preferred language."""
    _lang_cache[telegram_id] = lang


def set_token_cache(telegram_id: int, token: str) -> None:
    """Store the per-employee bot session token issued by POST /bot/link."""
    _token_cache[telegram_id] = token


def _get_employee_headers(telegram_id: int) -> dict[str, str]:
    """
    Return headers for an employee-scoped request.
    Raises ApiError(401) if no token is cached for this telegram_id yet
    (employee must /start again after a bot restart).
    """
    token = _token_cache.get(telegram_id)
    if not token:
        raise ApiError(
            401,
            "\u0421\u0435\u0441\u0441\u0438\u044f \u0431\u043e\u0442\u0430 \u0438\u0441\u0442\u0435\u043a\u043b\u0430. "
            "\u041f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, "
            "\u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 /start \u0434\u043b\u044f "
            "\u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0439 \u0430\u0443\u0442\u0435\u043d\u0442\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u0438.",
        )
    return {**_BASE_HEADERS, "X-Bot-Employee-Token": token}


# ---- Internal httpx helpers --------------------------------------------------

def _base_client() -> httpx.AsyncClient:
    """Client with bot-level secret only (no employee token)."""
    return httpx.AsyncClient(base_url=BACKEND_URL, headers=_BASE_HEADERS, timeout=15.0)


def _emp_client(telegram_id: int) -> httpx.AsyncClient:
    """Client with both bot secret and per-employee token."""
    return httpx.AsyncClient(
        base_url=BACKEND_URL,
        headers=_get_employee_headers(telegram_id),
        timeout=15.0,
    )


async def _handle(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(resp.status_code, str(detail))
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


# ---- Language cache ----------------------------------------------------------

async def get_employee_lang(telegram_id: int) -> str:
    """
    Return the employee's preferred language ("ru" | "uz" | "en").
    Uses an in-memory cache; falls back to "ru" on any error.
    """
    if telegram_id in _lang_cache:
        return _lang_cache[telegram_id]
    try:
        me = await get_me(telegram_id)
        lang: str = me.get("preferred_language") or "ru"
        _lang_cache[telegram_id] = lang
        return lang
    except ApiError:
        return "ru"


# ---- Bot-level endpoints (no employee token) ---------------------------------

async def link_account(telegram_id: int, invite_code: str) -> dict[str, Any]:
    """
    POST /bot/link — link a Telegram account to an employee profile.
    Returns BotLinkResponse which includes bot_session_token.
    The caller MUST call set_token_cache() with the returned token.
    """
    async with _base_client() as c:
        resp = await c.post("/bot/link", json={"telegram_id": telegram_id, "invite_code": invite_code})
        return await _handle(resp)


# ---- Employee-scoped endpoints (require X-Bot-Employee-Token) ----------------

async def get_me(telegram_id: int) -> dict[str, Any]:
    async with _emp_client(telegram_id) as c:
        resp = await c.get("/bot/me")
        return await _handle(resp)


async def list_checklists_today(telegram_id: int) -> list[dict[str, Any]]:
    async with _emp_client(telegram_id) as c:
        resp = await c.get("/bot/checklists/today")
        return await _handle(resp)


async def get_current_item(
    telegram_id: int, checklist_id: int, lang: str = "ru"
) -> dict[str, Any] | None:
    async with _emp_client(telegram_id) as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/current-item",
            params={"lang": lang},
        )
        return await _handle(resp)


async def get_item(telegram_id: int, checklist_id: int, item_id: int) -> dict[str, Any]:
    async with _emp_client(telegram_id) as c:
        resp = await c.get(f"/bot/checklists/{checklist_id}/items/{item_id}")
        return await _handle(resp)


async def toggle_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/toggle",
            json={"note": note},
        )
        return await _handle(resp)


async def skip_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/skip",
            json={"note": note},
        )
        return await _handle(resp)


async def upload_item_photo(
    telegram_id: int, checklist_id: int, item_id: int, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    async with _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/photo",
            files={"file": (filename, file_bytes, "image/jpeg")},
        )
        return await _handle(resp)
