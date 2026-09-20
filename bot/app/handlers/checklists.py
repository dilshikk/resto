from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import api_client
from app.api_client import ApiError
from app.keyboards import (
    back_to_list_keyboard,
    checklists_keyboard,
    item_keyboard,
    photo_checklist_keyboard,
    photo_confirm_keyboard,
)
from app.states import ItemStates, PhotoStates

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


# ── Standalone photo — safe two-step flow ─────────────────────────────────────
#
# Old behaviour: silently attach the photo to the first pending checklist's
# current item with no confirmation.  If the employee had several active
# checklists the photo would go to the wrong one.
#
# New behaviour (FSM):
#   Step 0 — receive_standalone_photo()
#     • 0 pending checklists → explain and exit.
#     • 1 pending checklist, but no pending item → tell user and exit.
#     • 1 pending checklist with a pending item → jump straight to the
#       confirmation step (PhotoStates.waiting_for_confirmation).
#     • 2+ pending checklists → ask the user to pick one first
#       (PhotoStates.waiting_for_checklist_choice).
#     The Telegram file_id is stored in FSM state; the actual download
#     happens only after the user confirms, saving bandwidth on cancels.
#
#   Step 1a — photo_checklist_chosen() [only when 2+ checklists]
#     Resolve the chosen checklist's current item and move to the
#     confirmation step.
#
#   Step 1b — photo_confirmed() [confirmation]
#     Download, upload to the API, show result, clear state.
#
#   Cancel — photo_cancelled() [any step]
#     Clear state, tell the user the photo was discarded.

@router.message(F.photo)
async def receive_standalone_photo(message: Message, state: FSMContext) -> None:
    """
    Entry point for a photo sent outside any active FSM state.

    Stores the Telegram file_id in FSM state (no download yet) and
    routes to either the checklist-picker or the confirmation step.
    """
    telegram_id = message.from_user.id
    try:
        checklists = await api_client.list_checklists_today(telegram_id)
    except ApiError as e:
        await message.answer(f"Не удалось определить чек-лист: {e.detail}")
        return

    pending = [c for c in checklists if c["status"] != "completed"]
    if not pending:
        await message.answer(
            "Нет активных чек-листов, к которым можно приложить фото.\n"
            "Отправьте /today, чтобы увидеть список."
        )
        return

    # Store the file_id — download only after the user confirms.
    file_id = message.photo[-1].file_id
    await state.update_data(file_id=file_id)

    if len(pending) == 1:
        # One active checklist — skip straight to confirmation.
        checklist_id = pending[0]["id"]
        item = await api_client.get_current_item(telegram_id, checklist_id)
        if item is None:
            await state.clear()
            await message.answer(
                "В активном чек-листе все пункты уже выполнены. "
                "Фото не прикреплено."
            )
            return
        await state.update_data(checklist_id=checklist_id, item_id=item["id"])
        await state.set_state(PhotoStates.waiting_for_confirmation)
        await message.answer(
            f"Прикрепить фото к текущему пункту?\n\n"
            f"📋 {pending[0]['template_name']} → «{item['title']}»",
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )
    else:
        # Several active checklists — ask the user to pick the right one.
        await state.set_state(PhotoStates.waiting_for_checklist_choice)
        await message.answer(
            "У вас несколько активных чек-листов. К какому прикрепить фото?",
            reply_markup=photo_checklist_keyboard(pending),
        )


@router.callback_query(PhotoStates.waiting_for_checklist_choice, F.data.startswith("photo_cl:"))
async def photo_checklist_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    """User picked a checklist from the list — resolve its current item."""
    await callback.answer()
    checklist_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    item = await api_client.get_current_item(telegram_id, checklist_id)
    if item is None:
        await state.clear()
        await callback.message.answer(
            "В выбранном чек-листе нет невыполненных пунктов. "
            "Фото не прикреплено."
        )
        return

    await state.update_data(checklist_id=checklist_id, item_id=item["id"])
    await state.set_state(PhotoStates.waiting_for_confirmation)

    # Try to edit the original message instead of flooding with new ones.
    try:
        await callback.message.edit_text(
            f"Прикрепить фото к текущему пункту?\n\n"
            f"📋 → «{item['title']}»",
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )
    except Exception:
        await callback.message.answer(
            f"Прикрепить фото к текущему пункту?\n\n"
            f"📋 → «{item['title']}»",
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )


@router.callback_query(PhotoStates.waiting_for_confirmation, F.data.startswith("photo_confirm:"))
async def photo_confirmed(callback: CallbackQuery, state: FSMContext, bot) -> None:  # noqa: ANN001
    """User confirmed — download and upload the photo."""
    await callback.answer()
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    item_id = data["item_id"]
    file_id = data["file_id"]
    telegram_id = callback.from_user.id

    await state.clear()

    # Resolve a fresh item title for the confirmation message.
    item = await api_client.get_current_item(telegram_id, checklist_id)
    item_title = item["title"] if item else "пункт"

    try:
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        await api_client.upload_item_photo(
            telegram_id, checklist_id, item_id, file_bytes.read(), "confirm.jpg"
        )
    except ApiError as e:
        await callback.message.answer(f"Не удалось сохранить фото: {e.detail}")
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(f"Фото прикреплено к пункту «{item_title}» ✅")


@router.callback_query(F.data == "photo_cancel")
async def photo_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    """User cancelled at any step of the photo flow."""
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer("Фото отменено. Отправьте /today, чтобы продолжить работу.")
