"""Thin async client for the backend's /api/v1/bot/* endpoints.

Authentication model
--------------------
Every request carries two credentials:
  X-Bot-Secret            -- proves the request comes from *our* bot service
  X-Bot-Employee-Token    -- per-employee token issued by POST /bot/link or
                             POST /bot/resync (required on all endpoints
                             except /bot/link and /bot/resync themselves)

The plaintext token is stored in-memory keyed by telegram_id.  On bot
restart the cache is empty. Rather than dead-ending the employee, the first
command that needs an employee token calls _ensure_token(), which -- on a
cache miss -- transparently calls POST /bot/resync to mint a fresh token for
an already-linked telegram_id (no invite code needed, since Telegram itself
already authenticates the caller). Only a genuinely never-linked telegram_id
(resync returns 404) falls through to asking for an invite code.
"""
from typing import Any

import httpx

from app.config import BACKEND_URL, BOT_INTERNAL_SECRET

# Base headers sent on every request (bot-level authentication).
_BASE_HEADERS = {"X-Bot-Secret": BOT_INTERNAL_SECRET}

# In-memory caches keyed by telegram_id.
# Both are populated when an employee links their account or on first
# successful /bot/me call.  Both are lost on bot restart -- _ensure_token()
# is what makes that loss recoverable instead of a dead end.
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
    """Store the per-employee bot session token issued by /bot/link or /bot/resync."""
    _token_cache[telegram_id] = token


async def _ensure_token(telegram_id: int) -> str:
    """
    Return a valid session token for *telegram_id*, resyncing with the
    backend on a cache miss (e.g. right after a bot restart).

    Raises ApiError(404) only when the backend confirms this telegram_id has
    never been linked to an employee -- the only case where asking for an
    invite code is actually correct.
    """
    token = _token_cache.get(telegram_id)
    if token:
        return token

    result = await resync_account(telegram_id)
    fresh_token: str = result.get("bot_session_token", "")
    if not fresh_token:
        # Should not happen if the backend call succeeded, but guard anyway.
        raise ApiError(401, "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c \u0441\u0435\u0441\u0441\u0438\u044e.")
    set_token_cache(telegram_id, fresh_token)
    emp_lang = result.get("preferred_language")
    if emp_lang:
        set_lang_cache(telegram_id, emp_lang)
    return fresh_token


def _get_employee_headers(token: str) -> dict[str, str]:
    return {**_BASE_HEADERS, "X-Bot-Employee-Token": token}


# ---- Internal httpx helpers --------------------------------------------------

def _base_client() -> httpx.AsyncClient:
    """Client with bot-level secret only (no employee token)."""
    return httpx.AsyncClient(base_url=BACKEND_URL, headers=_BASE_HEADERS, timeout=15.0)


async def _emp_client(telegram_id: int) -> httpx.AsyncClient:
    """Client with both bot secret and per-employee token, resyncing first if needed."""
    token = await _ensure_token(telegram_id)
    return httpx.AsyncClient(
        base_url=BACKEND_URL,
        headers=_get_employee_headers(token),
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


async def resync_account(telegram_id: int) -> dict[str, Any]:
    """
    POST /bot/resync — silently re-issue a session token for a telegram_id
    that is already linked to an employee (no invite code required).

    This is what recovers employees after a bot restart wipes the in-memory
    _token_cache: the old /bot/link flow would otherwise reject them with
    409 "Telegram already linked" forever, since employees.telegram_id stays
    set in the database. Raises ApiError(404) if this telegram_id was never
    linked -- callers should fall back to the invite-code flow in that case.
    """
    async with _base_client() as c:
        resp = await c.post("/bot/resync", json={"telegram_id": telegram_id})
        return await _handle(resp)


# ---- Employee-scoped endpoints (require X-Bot-Employee-Token) ----------------

async def get_me(telegram_id: int) -> dict[str, Any]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.get("/bot/me")
        return await _handle(resp)


async def list_checklists_today(telegram_id: int) -> list[dict[str, Any]]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.get("/bot/checklists/today")
        return await _handle(resp)


async def get_current_item(
    telegram_id: int, checklist_id: int, lang: str = "ru"
) -> dict[str, Any] | None:
    async with await _emp_client(telegram_id) as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/current-item",
            params={"lang": lang},
        )
        return await _handle(resp)


async def get_item(telegram_id: int, checklist_id: int, item_id: int) -> dict[str, Any]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.get(f"/bot/checklists/{checklist_id}/items/{item_id}")
        return await _handle(resp)


async def toggle_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/toggle",
            json={"note": note},
        )
        return await _handle(resp)


async def skip_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/skip",
            json={"note": note},
        )
        return await _handle(resp)


async def upload_item_photo(
    telegram_id: int, checklist_id: int, item_id: int, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    async with await _emp_client(telegram_id) as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/photo",
            files={"file": (filename, file_bytes, "image/jpeg")},
        )
        return await _handle(resp)
