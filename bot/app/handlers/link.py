from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import api_client
from app.api_client import ApiError
from app.i18n import get_lang, t
from app.states import LinkStates

router = Router(name="link")


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


@router.message(CommandStart(deep_link=True))
async def start_with_code(message: Message, command: CommandObject, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    lang = get_lang(message.from_user.language_code)
    code = (command.args or "").strip()

    # Try to greet if already linked (token may be in cache from previous session)
    try:
        await _greet_linked_employee(message, telegram_id, lang)
        return
    except ApiError as e:
        # 401 = session token missing/expired; 404 = not linked yet
        if e.status_code not in (401, 404):
            await message.answer(t("error_generic", lang, detail=e.detail))
            return

    if not code:
        await state.set_state(LinkStates.waiting_for_code)
        await message.answer(t("ask_for_code", lang))
        return

    await _try_link(message, telegram_id, code, state, lang)


@router.message(CommandStart())
async def start_plain(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    lang = get_lang(message.from_user.language_code)
    try:
        await _greet_linked_employee(message, telegram_id, lang)
        return
    except ApiError as e:
        if e.status_code not in (401, 404):
            await message.answer(t("error_generic", lang, detail=e.detail))
            return

    await state.set_state(LinkStates.waiting_for_code)
    await message.answer(t("ask_for_code", lang))


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
