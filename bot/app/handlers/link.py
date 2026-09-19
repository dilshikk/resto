from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import api_client
from app.api_client import ApiError
from app.states import LinkStates

router = Router(name="link")


WELCOME_LINKED = (
    "Здравствуйте, {name}! 👋\n\n"
    "Должность: {role}\n"
    "Филиал: {branch}\n\n"
    "Команда /today покажет ваши чек-листы на сегодня."
)

ASK_FOR_CODE = (
    "Здравствуйте! 👋 Это бот MADO Checklist.\n\n"
    "Чтобы начать, отправьте код приглашения, который вам дал менеджер "
    "(8 символов, например ABC123XY)."
)


async def _greet_linked_employee(message: Message, telegram_id: int) -> None:
    me = await api_client.get_me(telegram_id)
    await message.answer(
        WELCOME_LINKED.format(name=me["full_name"], role=me["role_name"], branch=me["primary_branch_name"])
    )


@router.message(CommandStart(deep_link=True))
async def start_with_code(message: Message, command: CommandObject, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    code = (command.args or "").strip()

    try:
        await _greet_linked_employee(message, telegram_id)
        return
    except ApiError as e:
        if e.status_code != 404:
            await message.answer(f"Произошла ошибка: {e.detail}")
            return
        # not linked yet — fall through to link with the code from the deep link

    if not code:
        await state.set_state(LinkStates.waiting_for_code)
        await message.answer(ASK_FOR_CODE)
        return

    await _try_link(message, telegram_id, code, state)


@router.message(CommandStart())
async def start_plain(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    try:
        await _greet_linked_employee(message, telegram_id)
        return
    except ApiError as e:
        if e.status_code != 404:
            await message.answer(f"Произошла ошибка: {e.detail}")
            return

    await state.set_state(LinkStates.waiting_for_code)
    await message.answer(ASK_FOR_CODE)


@router.message(LinkStates.waiting_for_code, F.text)
async def receive_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    await _try_link(message, message.from_user.id, code, state)


async def _try_link(message: Message, telegram_id: int, code: str, state: FSMContext) -> None:
    if not code:
        await message.answer("Пожалуйста, отправьте код приглашения текстом.")
        return
    try:
        me = await api_client.link_account(telegram_id, code)
    except ApiError as e:
        if e.status_code == 404:
            await message.answer("Код приглашения не найден. Проверьте код и попробуйте снова.")
        elif e.status_code == 409:
            await message.answer(f"{e.detail}")
        else:
            await message.answer(f"Не удалось привязать аккаунт: {e.detail}")
        return

    await state.clear()
    await message.answer(
        f"Готово! Аккаунт привязан ✅\n\n"
        f"Должность: {me['role_name']}\nФилиал: {me['primary_branch_name']}\n\n"
        f"Команда /today покажет ваши чек-листы на сегодня."
    )
