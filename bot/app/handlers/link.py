from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import api_client
from app.api_client import ApiError
from app.i18n import get_lang, t
from app.keyboards import (
    CHOOSE_LANGUAGE_TEXT,
    language_keyboard,
    remove_keyboard,
    share_contact_keyboard,
)
from app.states import LinkStates, RegisterStates

router = Router(name="link")

_VALID_LANGS = frozenset({"ru", "uz", "en"})


async def _greet_linked_employee(message: Message, telegram_id: int, lang: str) -> None:
    me = await api_client.get_me(telegram_id)
    emp_lang = me.get("preferred_language") or lang
    api_client.set_lang_cache(telegram_id, emp_lang)
    await message.answer(
        t("welcome_linked", emp_lang,
          name=me["full_name"],
          role=me["role_name"],
          branch=me["primary_branch_name"])
    )


async def _try_greet(message: Message, telegram_id: int, lang: str) -> bool:
    """
    Greet an already-linked employee. Returns False when the employee is not
    linked (401/404), or is linked but no longer active (403), so the caller
    continues with the registration/status flow instead of surfacing the raw
    resync error.

    On 401 the cached session token is dropped: it may belong to an employee
    that was deleted from the web panel. Without this, the same person would
    keep the stale token after re-registering and being approved again.
    """
    try:
        await _greet_linked_employee(message, telegram_id, lang)
        return True
    except ApiError as e:
        if e.status_code == 401:
            api_client.clear_session(telegram_id)
            return False
        if e.status_code in (403, 404):
            return False
        raise


async def _handle_unlinked_start(
    message: Message, telegram_id: int, code: str, state: FSMContext, lang: str
) -> None:
    """
    Reached when the employee has no valid bot session token yet (never
    linked, or 401/404 from _greet_linked_employee).

    - If a deep-link invite code was supplied, keep the existing
      manager-first flow: try to link immediately.
    - Otherwise, ask the backend for this telegram_id's registration status
      and branch on it:
        not_registered -> choose language, then share contact
        pending/blocked/archived/inactive/fired -> show a status message
        active -> should not happen here (means a stale/missing token);
                  fall back to greeting via /bot/resync through get_me.
    """
    if code:
        await _try_link(message, telegram_id, code, state, lang)
        return

    try:
        status = await api_client.get_registration_status(telegram_id)
    except ApiError as e:
        await message.answer(t("error_generic", lang, detail=e.detail))
        return

    reg_status = status.get("status")
    status_lang = status.get("preferred_language") or lang
    name = status.get("full_name") or ""

    if reg_status == "not_registered":
        # First contact with the bot: let the employee pick a language
        # before anything else, so every following message is readable.
        await state.clear()
        await state.set_state(RegisterStates.choosing_language)
        await message.answer(CHOOSE_LANGUAGE_TEXT, reply_markup=language_keyboard())
        return

    if reg_status == "pending":
        await message.answer(t("status_pending", status_lang, name=name))
        return

    if reg_status in ("blocked", "inactive", "fired"):
        await message.answer(t("status_blocked", status_lang, name=name))
        return

    if reg_status == "archived":
        await message.answer(t("status_archived", status_lang, name=name))
        return

    # reg_status == "active" but we still couldn't greet (e.g. a race right
    # after approval, before the bot has a session token). Ask the employee
    # to send /start again so _greet_linked_employee's resync path can run.
    await state.set_state(LinkStates.waiting_for_code)
    await message.answer(t("ask_for_code", lang))


async def _start(message: Message, state: FSMContext, code: str) -> None:
    telegram_id = message.from_user.id
    lang = get_lang(message.from_user.language_code)
    try:
        if await _try_greet(message, telegram_id, lang):
            return
    except ApiError as e:
        await message.answer(t("error_generic", lang, detail=e.detail))
        return

    await _handle_unlinked_start(message, telegram_id, code, state, lang)


@router.message(CommandStart(deep_link=True))
async def start_with_code(message: Message, command: CommandObject, state: FSMContext) -> None:
    await _start(message, state, (command.args or "").strip())


@router.message(CommandStart())
async def start_plain(message: Message, state: FSMContext) -> None:
    await _start(message, state, "")


@router.message(LinkStates.waiting_for_code, F.text)
async def receive_code(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.language_code)
    code = (message.text or "").strip()
    await _try_link(message, message.from_user.id, code, state, lang)


async def _try_link(
    message: Message,
    telegram_id: int,
    code: str,
    state: FSMContext,
    lang: str,
) -> None:
    if not code:
        await message.answer(t("ask_code_text", lang))
        return
    try:
        result = await api_client.link_account(telegram_id, code)
    except ApiError as e:
        if e.status_code == 404:
            await message.answer(t("code_not_found", lang))
        elif e.status_code == 409:
            await message.answer(e.detail)
        else:
            await message.answer(t("link_error", lang, detail=e.detail))
        return

    # Store the per-employee session token returned by the backend.
    # This token is required for all subsequent employee-scoped API calls.
    bot_token: str = result.get("bot_session_token", "")
    if bot_token:
        api_client.set_token_cache(telegram_id, bot_token)

    await state.clear()
    emp_lang = result.get("preferred_language") or lang
    api_client.set_lang_cache(telegram_id, emp_lang)
    await message.answer(
        t("account_linked", emp_lang,
          role=result["role_name"],
          branch=result["primary_branch_name"])
    )


# ── Self-service registration: language step ───────────────────────────────

@router.callback_query(RegisterStates.choosing_language, F.data.startswith("lang:"))
async def choose_language(callback: CallbackQuery, state: FSMContext) -> None:
    lang = (callback.data or "").split(":", 1)[1]
    if lang not in _VALID_LANGS:
        lang = "ru"

    await state.update_data(lang=lang)
    await state.set_state(RegisterStates.waiting_for_contact)
    await callback.answer()
    # Remove the language buttons so they can't be pressed twice.
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            t("ask_share_contact", lang),
            reply_markup=share_contact_keyboard(lang),
        )


@router.message(RegisterStates.choosing_language)
async def choose_language_wrong_input(message: Message) -> None:
    await message.answer(CHOOSE_LANGUAGE_TEXT, reply_markup=language_keyboard())


async def _registration_lang(message: Message, state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("lang") or get_lang(message.from_user.language_code)


# ── Self-service registration: contact-sharing step ─────────────────────────

@router.message(RegisterStates.waiting_for_contact, F.contact)
async def receive_contact(message: Message, state: FSMContext) -> None:
    """
    Employee tapped "Share contact". Telegram guarantees message.contact
    belongs to the sender when it comes from the native request_contact
    button, so we trust its phone_number/user_id here.
    """
    telegram_id = message.from_user.id
    lang = await _registration_lang(message, state)
    contact = message.contact

    full_name = " ".join(
        part for part in (contact.first_name, contact.last_name) if part
    ).strip() or (message.from_user.full_name or "Без имени")

    try:
        result = await api_client.register_account(
            telegram_id=telegram_id,
            full_name=full_name,
            username=message.from_user.username,
            phone=contact.phone_number,
            preferred_language=lang,
        )
    except ApiError as e:
        await message.answer(t("registration_error", lang, detail=e.detail), reply_markup=remove_keyboard())
        return

    await state.clear()
    reg_lang = result.get("preferred_language") or lang
    api_client.set_lang_cache(telegram_id, reg_lang)
    await message.answer(
        t("registration_pending", reg_lang, name=result.get("full_name") or full_name),
        reply_markup=remove_keyboard(),
    )


@router.message(RegisterStates.waiting_for_contact)
async def receive_contact_wrong_input(message: Message, state: FSMContext) -> None:
    """Employee sent something other than a shared contact — re-prompt."""
    lang = await _registration_lang(message, state)
    await message.answer(t("contact_wrong_input", lang), reply_markup=share_contact_keyboard(lang))
