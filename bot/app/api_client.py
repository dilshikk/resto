"""Thin async client for the backend's /api/v1/bot/* endpoints."""
from typing import Any

import httpx

from app.config import BACKEND_URL, BOT_INTERNAL_SECRET

_HEADERS = {"X-Bot-Secret": BOT_INTERNAL_SECRET}

# In-memory cache: telegram_id -> preferred_language ("ru"|"uz"|"en")
# Populated on first get_me() call and on account linking.
# Cleared on bot restart — the next command will re-fetch.
_lang_cache: dict[int, str] = {}


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BACKEND_URL, headers=_HEADERS, timeout=15.0)


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


def set_lang_cache(telegram_id: int, lang: str) -> None:
    """Explicitly cache a user's preferred language (call after link / get_me)."""
    _lang_cache[telegram_id] = lang


async def get_employee_lang(telegram_id: int) -> str:
    """
    Return the employee's preferred language ("ru" | "uz" | "en").
    Uses an in-memory cache to avoid an extra round-trip on every message.
    Falls back to "ru" if the employee is not linked or the request fails.
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


async def link_account(telegram_id: int, invite_code: str) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.post("/bot/link", json={"telegram_id": telegram_id, "invite_code": invite_code})
        return await _handle(resp)


async def get_me(telegram_id: int) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.get("/bot/me", params={"telegram_id": telegram_id})
        return await _handle(resp)


async def list_checklists_today(telegram_id: int) -> list[dict[str, Any]]:
    async with _client() as c:
        resp = await c.get("/bot/checklists/today", params={"telegram_id": telegram_id})
        return await _handle(resp)


async def get_current_item(
    telegram_id: int, checklist_id: int, lang: str = "ru"
) -> dict[str, Any] | None:
    async with _client() as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/current-item",
            params={"telegram_id": telegram_id, "lang": lang},
        )
        return await _handle(resp)


async def get_item(telegram_id: int, checklist_id: int, item_id: int) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/items/{item_id}", params={"telegram_id": telegram_id}
        )
        return await _handle(resp)


async def toggle_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/toggle",
            json={"telegram_id": telegram_id, "note": note},
        )
        return await _handle(resp)


async def skip_item(
    telegram_id: int, checklist_id: int, item_id: int, note: str | None = None
) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/skip",
            json={"telegram_id": telegram_id, "note": note},
        )
        return await _handle(resp)


async def upload_item_photo(
    telegram_id: int, checklist_id: int, item_id: int, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/photo",
            data={"telegram_id": str(telegram_id)},
            files={"file": (filename, file_bytes, "image/jpeg")},
        )
        return await _handle(resp)
