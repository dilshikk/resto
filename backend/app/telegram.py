"""
Thin helper for sending Telegram messages directly from the backend.

Used for push notifications that must arrive even when the employee has
no active bot session (e.g. approve / reject on self-registration), and
for PDF checklist reports sent to the managers' group.

All calls are fire-and-forget: failures are logged but never bubble up
to the caller so that a Telegram outage never breaks an API response.

Requires BOT_TOKEN to be set in the environment.  When the token is
absent every call is a no-op (useful for local dev without a real bot).
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org"

# ── Localised message templates ───────────────────────────────────────────────

_APPROVED: dict[str, str] = {
    "ru": (
        "✅ Ваша заявка одобрена!\n\n"
        "Должность: {role}\n"
        "Филиал: {branch}\n\n"
        "Отправьте /start, чтобы начать работу."
    ),
    "uz": (
        "✅ So'rovingiz tasdiqlandi!\n\n"
        "Lavozim: {role}\n"
        "Filial: {branch}\n\n"
        "Boshlash uchun /start yuboring."
    ),
    "en": (
        "✅ Your request has been approved!\n\n"
        "Position: {role}\n"
        "Branch: {branch}\n\n"
        "Send /start to get started."
    ),
}

_REJECTED: dict[str, str] = {
    "ru": (
        "❌ Ваша заявка отклонена.\n\n"
        "К сожалению, менеджер отклонил вашу заявку.\n"
        "Если это ошибка — обратитесь в ресторан напрямую."
    ),
    "uz": (
        "❌ So'rovingiz rad etildi.\n\n"
        "Afsuski, menejer so'rovingizni rad etdi.\n"
        "Bu xato bo'lsa — restoran bilan bevosita bog'laning."
    ),
    "en": (
        "❌ Your request has been rejected.\n\n"
        "Unfortunately, the manager declined your request.\n"
        "If this is a mistake, please contact the restaurant directly."
    ),
}


async def _send_message(chat_id: int, text: str) -> None:
    """
    Send a text message to *chat_id* via the Telegram Bot API.
    Silently swallows all errors so callers are never affected.
    """
    token = settings.BOT_TOKEN
    if not token:
        logger.debug("BOT_TOKEN not set — skipping Telegram push to chat_id=%d", chat_id)
        return

    url = f"{_TG_API}/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            if resp.status_code != 200:
                logger.warning(
                    "Telegram sendMessage failed: chat_id=%d status=%d body=%s",
                    chat_id, resp.status_code, resp.text[:200],
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram sendMessage error: chat_id=%d error=%s", chat_id, exc)


async def send_document(chat_id: int, file_bytes: bytes, filename: str, caption: str | None = None) -> None:
    """
    Send a file (e.g. a PDF report) to *chat_id* via sendDocument.
    Silently swallows all errors so callers are never affected.
    """
    token = settings.BOT_TOKEN
    if not token:
        logger.debug("BOT_TOKEN not set — skipping Telegram document to chat_id=%d", chat_id)
        return

    url = f"{_TG_API}/bot{token}/sendDocument"
    data: dict[str, str] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]  # Telegram caption limit
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url, data=data, files={"document": (filename, file_bytes, "application/pdf")}
            )
            if resp.status_code != 200:
                logger.warning(
                    "Telegram sendDocument failed: chat_id=%d status=%d body=%s",
                    chat_id, resp.status_code, resp.text[:200],
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram sendDocument error: chat_id=%d error=%s", chat_id, exc)


async def notify_employee_approved(
    telegram_id: int | None,
    lang: str,
    role_name: str,
    branch_name: str,
) -> None:
    """
    Notify an employee that their self-registration request was approved.
    No-op when *telegram_id* is None.
    """
    if telegram_id is None:
        return
    template = _APPROVED.get(lang) or _APPROVED["ru"]
    await _send_message(telegram_id, template.format(role=role_name, branch=branch_name))


async def notify_employee_rejected(
    telegram_id: int | None,
    lang: str,
) -> None:
    """
    Notify an employee that their self-registration request was rejected.
    No-op when *telegram_id* is None.
    """
    if telegram_id is None:
        return
    text = _REJECTED.get(lang) or _REJECTED["ru"]
    await _send_message(telegram_id, text)
