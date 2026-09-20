from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import api_client
from app.api_client import ApiError
from app.i18n import get_lang, t
from app.keyboards import (
    back_to_list_keyboard,
    checklists_keyboard,
    item_keyboard,
    photo_checklist_keyboard,
    photo_confirm_keyboard,
)
from app.states import ItemStates, PhotoStates

router = Router(name="checklists")

# Telegram's own hard limit is 20 MB, but the backend rejects anything over 8 MB.
# We check here so we never download a file we know the backend will refuse.
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 MB


def _item_text(item: dict, lang: str) -> str:
    lines = [
        t("step_header", lang, current=item["current_position"], total=item["total_items"]),
        "",
        f"\ud83d\udccb {item['title']}",
    ]
    if item.get("description"):
        lines.append(item["description"])
    if item.get("standard_title"):
        lines.append("\n" + t("standard_label", lang, title=item["standard_title"]))
    if not item["is_required"]:
        lines.append("\n" + t("optional_item", lang))
    return "\n".join(lines)


async def _show_current_item_or_finish(
    target: Message | CallbackQuery,
    telegram_id: int,
    checklist_id: int,
    lang: str,
) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    item = await api_client.get_current_item(telegram_id, checklist_id)
    if item is None:
        await message.answer(
            t("checklist_done", lang),
            reply_markup=back_to_list_keyboard(),
        )
        return
    await message.answer(
        _item_text(item, lang),
        reply_markup=item_keyboard(checklist_id, item["id"], is_required=item["is_required"]),
    )


async def _download_photo(bot, file_id: str, lang: str, message: Message) -> bytes | None:
    """
    Resolve the Telegram file object, check its size, then download it.
    Returns the raw bytes on success, or None after sending an error reply.
    """
    file = await bot.get_file(file_id)
    size = file.file_size or 0
    if size > MAX_PHOTO_BYTES:
        mb = size / (1024 * 1024)
        await message.answer(t("photo_too_large", lang, size_mb=f"{mb:.1f}"))
        return None
    buf = await bot.download_file(file.file_path)
    return buf.read()


@router.message(F.text == "/today")
async def show_today(message: Message) -> None:
    lang = get_lang(message.from_user.language_code)
    await _send_checklists_list(message, message.from_user.id, lang)


async def _send_checklists_list(message: Message, telegram_id: int, lang: str) -> None:
    try:
        checklists = await api_client.list_checklists_today(telegram_id)
    except ApiError as e:
        if e.status_code == 404:
            await message.answer(t("not_linked", lang))
        else:
            await message.answer(t("checklists_error", lang, detail=e.detail))
        return

    if not checklists:
        await message.answer(t("no_checklists", lang))
        return

    await message.answer(t("checklists_today", lang), reply_markup=checklists_keyboard(checklists))


@router.callback_query(F.data == "back:checklists")
async def back_to_checklists(callback: CallbackQuery) -> None:
    await callback.answer()
    lang = get_lang(callback.from_user.language_code)
    await _send_checklists_list(callback.message, callback.from_user.id, lang)


@router.callback_query(F.data.startswith("cl:"))
async def open_checklist(callback: CallbackQuery) -> None:
    await callback.answer()
    lang = get_lang(callback.from_user.language_code)
    checklist_id = int(callback.data.split(":")[1])
    await _show_current_item_or_finish(callback, callback.from_user.id, checklist_id, lang)


@router.callback_query(F.data.startswith("done:"))
async def mark_done(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.language_code)
    _, checklist_id, item_id = callback.data.split(":")
    try:
        await api_client.toggle_item(callback.from_user.id, int(checklist_id), int(item_id))
    except ApiError as e:
        await callback.answer(e.detail, show_alert=True)
        return
    await callback.answer(t("item_done", lang))
    await _show_current_item_or_finish(callback, callback.from_user.id, int(checklist_id), lang)


@router.callback_query(F.data.startswith("skip:"))
async def skip_item(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.language_code)
    _, checklist_id, item_id = callback.data.split(":")
    try:
        await api_client.skip_item(callback.from_user.id, int(checklist_id), int(item_id))
    except ApiError as e:
        await callback.answer(e.detail, show_alert=True)
        return
    await callback.answer(t("item_skipped", lang))
    await _show_current_item_or_finish(callback, callback.from_user.id, int(checklist_id), lang)


@router.callback_query(F.data.startswith("problem:"))
async def ask_problem_comment(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    lang = get_lang(callback.from_user.language_code)
    _, checklist_id, item_id = callback.data.split(":")
    await state.set_state(ItemStates.waiting_for_problem_comment)
    await state.update_data(checklist_id=int(checklist_id), item_id=int(item_id), lang=lang)
    await callback.message.answer(t("ask_problem", lang))


@router.message(ItemStates.waiting_for_problem_comment, F.text)
async def receive_problem_comment(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = data["checklist_id"], data["item_id"]
    lang: str = data.get("lang") or get_lang(message.from_user.language_code)
    try:
        note = t("problem_prefix", lang, text=message.text)
        await api_client.toggle_item(message.from_user.id, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        await state.clear()
        return
    await state.clear()
    await message.answer(t("problem_saved", lang))
    await _show_current_item_or_finish(message, message.from_user.id, checklist_id, lang)


@router.message(ItemStates.waiting_for_problem_comment, F.photo)
async def receive_problem_photo(message: Message, state: FSMContext, bot) -> None:  # noqa: ANN001
    data = await state.get_data()
    checklist_id, item_id = data["checklist_id"], data["item_id"]
    lang: str = data.get("lang") or get_lang(message.from_user.language_code)

    raw = await _download_photo(bot, message.photo[-1].file_id, lang, message)
    if raw is None:
        await state.clear()
        return

    try:
        await api_client.upload_item_photo(
            message.from_user.id, checklist_id, item_id, raw, "problem.jpg"
        )
        caption = message.caption
        note = t("problem_prefix", lang, text=caption) if caption else t("problem_photo", lang)
        await api_client.toggle_item(message.from_user.id, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        await state.clear()
        return
    await state.clear()
    await message.answer(t("photo_problem_saved", lang))
    await _show_current_item_or_finish(message, message.from_user.id, checklist_id, lang)


# ── Standalone photo — safe two-step flow ─────────────────────────────────────────────

@router.message(F.photo)
async def receive_standalone_photo(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.language_code)
    telegram_id = message.from_user.id
    try:
        checklists = await api_client.list_checklists_today(telegram_id)
    except ApiError as e:
        await message.answer(t("detect_checklist_error", lang, detail=e.detail))
        return

    pending = [c for c in checklists if c["status"] != "completed"]
    if not pending:
        await message.answer(t("no_active_checklists", lang))
        return

    # Check size before committing to the FSM flow.
    photo_size = message.photo[-1].file_size or 0
    if photo_size > MAX_PHOTO_BYTES:
        mb = photo_size / (1024 * 1024)
        await message.answer(t("photo_too_large", lang, size_mb=f"{mb:.1f}"))
        return

    file_id = message.photo[-1].file_id
    await state.update_data(file_id=file_id, lang=lang)

    if len(pending) == 1:
        checklist_id = pending[0]["id"]
        item = await api_client.get_current_item(telegram_id, checklist_id)
        if item is None:
            await state.clear()
            await message.answer(t("all_items_done", lang))
            return
        await state.update_data(checklist_id=checklist_id, item_id=item["id"])
        await state.set_state(PhotoStates.waiting_for_confirmation)
        await message.answer(
            t("photo_confirm", lang, template=pending[0]["template_name"], item=item["title"]),
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )
    else:
        await state.set_state(PhotoStates.waiting_for_checklist_choice)
        await message.answer(
            t("pick_checklist", lang),
            reply_markup=photo_checklist_keyboard(pending),
        )


@router.callback_query(PhotoStates.waiting_for_checklist_choice, F.data.startswith("photo_cl:"))
async def photo_checklist_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    checklist_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id
    data = await state.get_data()
    lang: str = data.get("lang") or get_lang(callback.from_user.language_code)

    item = await api_client.get_current_item(telegram_id, checklist_id)
    if item is None:
        await state.clear()
        await callback.message.answer(t("no_pending_items", lang))
        return

    await state.update_data(checklist_id=checklist_id, item_id=item["id"])
    await state.set_state(PhotoStates.waiting_for_confirmation)

    try:
        await callback.message.edit_text(
            t("photo_confirm_short", lang, item=item["title"]),
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )
    except Exception:
        await callback.message.answer(
            t("photo_confirm_short", lang, item=item["title"]),
            reply_markup=photo_confirm_keyboard(checklist_id, item["title"]),
        )


@router.callback_query(PhotoStates.waiting_for_confirmation, F.data.startswith("photo_confirm:"))
async def photo_confirmed(callback: CallbackQuery, state: FSMContext, bot) -> None:  # noqa: ANN001
    await callback.answer()
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    item_id = data["item_id"]
    file_id = data["file_id"]
    lang: str = data.get("lang") or get_lang(callback.from_user.language_code)
    telegram_id = callback.from_user.id

    await state.clear()

    item = await api_client.get_current_item(telegram_id, checklist_id)
    item_title = item["title"] if item else "—"

    raw = await _download_photo(bot, file_id, lang, callback.message)
    if raw is None:
        return

    try:
        await api_client.upload_item_photo(
            telegram_id, checklist_id, item_id, raw, "confirm.jpg"
        )
    except ApiError as e:
        await callback.message.answer(t("photo_save_error", lang, detail=e.detail))
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(t("photo_attached", lang, item=item_title))


@router.callback_query(F.data == "photo_cancel")
async def photo_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang: str = data.get("lang") or get_lang(callback.from_user.language_code)
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t("photo_cancelled", lang))
