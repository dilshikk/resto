"""Thin async client for the backend's /api/v1/bot/* endpoints."""
from typing import Any

import httpx

from app.config import BACKEND_URL, BOT_INTERNAL_SECRET

_HEADERS = {"X-Bot-Secret": BOT_INTERNAL_SECRET}


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


async def get_current_item(telegram_id: int, checklist_id: int) -> dict[str, Any] | None:
    async with _client() as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/current-item", params={"telegram_id": telegram_id}
        )
        return await _handle(resp)


async def get_item(telegram_id: int, checklist_id: int, item_id: int) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.get(
            f"/bot/checklists/{checklist_id}/items/{item_id}", params={"telegram_id": telegram_id}
        )
        return await _handle(resp)


async def toggle_item(telegram_id: int, checklist_id: int, item_id: int, note: str | None = None) -> dict[str, Any]:
    async with _client() as c:
        resp = await c.post(
            f"/bot/checklists/{checklist_id}/items/{item_id}/toggle",
            json={"telegram_id": telegram_id, "note": note},
        )
        return await _handle(resp)


async def skip_item(telegram_id: int, checklist_id: int, item_id: int, note: str | None = None) -> dict[str, Any]:
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
