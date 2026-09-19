from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import api_client
from app.api_client import ApiError
from app.keyboards import back_to_list_keyboard, checklists_keyboard, item_keyboard
from app.states import ItemStates

router = Router(name="checklists")


def _item_text(item: dict) -> str:
    lines = [
        f"Шаг {item['current_position']}/{item['total_items']}",
        "",
        f"📋 {item['title']}",
    ]
    if item.get("description"):
        lines.append(item["description"])
    if item.get("standard_title"):
        lines.append(f"\nСтандарт: {item['standard_title']}")
    if not item["is_required"]:
        lines.append("\n(необязательный пункт — можно пропустить)")
    return "\n".join(lines)


async def _show_current_item_or_finish(target: Message | CallbackQuery, telegram_id: int, checklist_id: int) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    item = await api_client.get_current_item(telegram_id, checklist_id)
    if item is None:
        await message.answer(
            "🎉 Все обязательные пункты этого чек-листа выполнены!\n"
            "Менеджер сможет закрыть чек-лист в веб-панели.",
            reply_markup=back_to_list_keyboard(),
        )
        return
    await message.answer(
        _item_text(item),
        reply_markup=item_keyboard(checklist_id, item["id"], is_required=item["is_required"]),
    )


@router.message(F.text == "/today")
async def show_today(message: Message) -> None:
    await _send_checklists_list(message, message.from_user.id)


async def _send_checklists_list(message: Message, telegram_id: int) -> None:
    try:
        checklists = await api_client.list_checklists_today(telegram_id)
    except ApiError as e:
        if e.status_code == 404:
            await message.answer("Сначала привяжите аккаунт: отправьте /start и код приглашения.")
        else:
            await message.answer(f"Не удалось получить чек-листы: {e.detail}")
        return

    if not checklists:
        await message.answer("На сегодня чек-листов нет. Загляните позже — менеджер их назначает по расписанию.")
        return

    await message.answer("Ваши чек-листы на сегодня:", reply_markup=checklists_keyboard(checklists))


@router.callback_query(F.data == "back:checklists")
async def back_to_checklists(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_checklists_list(callback.message, callback.from_user.id)


@router.callback_query(F.data.startswith("cl:"))
async def open_checklist(callback: CallbackQuery) -> None:
    await callback.answer()
    checklist_id = int(callback.data.split(":")[1])
    await _show_current_item_or_finish(callback, callback.from_user.id, checklist_id)


@router.callback_query(F.data.startswith("done:"))
async def mark_done(callback: CallbackQuery) -> None:
    _, checklist_id, item_id = callback.data.split(":")
    try:
        await api_client.toggle_item(callback.from_user.id, int(checklist_id), int(item_id))
    except ApiError as e:
        await callback.answer(e.detail, show_alert=True)
        return
    await callback.answer("Отмечено ✅")
    await _show_current_item_or_finish(callback, callback.from_user.id, int(checklist_id))


@router.callback_query(F.data.startswith("skip:"))
async def skip_item(callback: CallbackQuery) -> None:
    _, checklist_id, item_id = callback.data.split(":")
    try:
        await api_client.skip_item(callback.from_user.id, int(checklist_id), int(item_id))
    except ApiError as e:
        await callback.answer(e.detail, show_alert=True)
        return
    await callback.answer("Пропущено")
    await _show_current_item_or_finish(callback, callback.from_user.id, int(checklist_id))


@router.callback_query(F.data.startswith("problem:"))
async def ask_problem_comment(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    _, checklist_id, item_id = callback.data.split(":")
    await state.set_state(ItemStates.waiting_for_problem_comment)
    await state.update_data(checklist_id=int(checklist_id), item_id=int(item_id))
    await callback.message.answer(
        "Опишите проблему в двух словах (можно также прислать фото). Это добавится в чек-лист как комментарий."
    )


@router.message(ItemStates.waiting_for_problem_comment, F.text)
async def receive_problem_comment(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = data["checklist_id"], data["item_id"]
    try:
        await api_client.toggle_item(message.from_user.id, checklist_id, item_id, note=f"⚠️ Проблема: {message.text}")
    except ApiError as e:
        await message.answer(f"Не удалось сохранить: {e.detail}")
        await state.clear()
        return
    await state.clear()
    await message.answer("Записано, спасибо! Пункт отмечен с комментарием о проблеме.")
    await _show_current_item_or_finish(message, message.from_user.id, checklist_id)


@router.message(ItemStates.waiting_for_problem_comment, F.photo)
async def receive_problem_photo(message: Message, state: FSMContext, bot) -> None:  # noqa: ANN001
    data = await state.get_data()
    checklist_id, item_id = data["checklist_id"], data["item_id"]
    file = await bot.get_file(message.photo[-1].file_id)
    file_bytes = await bot.download_file(file.file_path)
    try:
        await api_client.upload_item_photo(
            message.from_user.id, checklist_id, item_id, file_bytes.read(), "problem.jpg"
        )
        note = f"⚠️ Проблема: {message.caption}" if message.caption else "⚠️ Проблема (фото)"
        await api_client.toggle_item(message.from_user.id, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(f"Не удалось сохранить: {e.detail}")
        await state.clear()
        return
    await state.clear()
    await message.answer("Фото и отметка о проблеме сохранены.")
    await _show_current_item_or_finish(message, message.from_user.id, checklist_id)


@router.message(F.photo)
async def receive_standalone_photo(message: Message, bot) -> None:  # noqa: ANN001
    """
    Photo sent outside a /problem flow: attach it to whichever item is currently
    pending across today's checklists best-effort — otherwise ask the user to open
    a checklist first via /today.
    """
    telegram_id = message.from_user.id
    try:
        checklists = await api_client.list_checklists_today(telegram_id)
    except ApiError as e:
        await message.answer(f"Не удалось определить чек-лист: {e.detail}")
        return

    pending = [c for c in checklists if c["status"] != "completed"]
    if not pending:
        await message.answer("Нет активных чек-листов, к которым можно приложить фото. Отправьте /today.")
        return

    checklist_id = pending[0]["id"]
    item = await api_client.get_current_item(telegram_id, checklist_id)
    if item is None:
        await message.answer("В текущем чек-листе все пункты уже выполнены.")
        return

    file = await bot.get_file(message.photo[-1].file_id)
    file_bytes = await bot.download_file(file.file_path)
    try:
        await api_client.upload_item_photo(telegram_id, checklist_id, item["id"], file_bytes.read(), "confirm.jpg")
    except ApiError as e:
        await message.answer(f"Не удалось сохранить фото: {e.detail}")
        return
    await message.answer(f"Фото прикреплено к пункту «{item['title']}» ✅")
