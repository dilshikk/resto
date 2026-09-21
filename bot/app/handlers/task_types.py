"""
Bot FSM handlers for non-checkbox task types.

Supported task types (beyond the default 'checkbox'):
  number      — employee enters a decimal number
  temperature — employee enters a decimal temperature value (°C)
  text        — employee types a free-text answer
  yes_no      — employee presses a Да/Нет inline-keyboard button
  photo       — employee sends a photo
  photo_geo   — employee sends a photo then a geolocation

The flow for each type:
  1. _advance_checklist() in checklists.py fetches the current item,
     detects item.task_type != 'checkbox', and calls the matching
     entry-point below.
  2. This module shows the prompt, stores (checklist_id, item_id) in FSM
     data, and sets the matching waiting_for_* state.
  3. On user response, this module validates the input, uploads/saves
     the result via the backend, and calls _advance_checklist() from
     checklists.py to show the next item.

Circular import between this module and checklists.py is handled with
deferred (in-function) imports where needed.
"""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.api_client import ApiError, get_employee_lang, toggle_item, upload_item_photo
from app.i18n import t
from app.keyboards import skip_location_keyboard, yes_no_keyboard

router = Router(name="task_types")

_MAX_PHOTO_BYTES = 25 * 1024 * 1024  # 25 MB


# ── FSM States ────────────────────────────────────────────────────────────

class TaskInputStates(StatesGroup):
    waiting_for_number_input      = State()
    waiting_for_temperature_input = State()
    waiting_for_text_input        = State()
    waiting_for_yes_no            = State()
    # photo task: waiting for a single photo
    waiting_for_photo_task        = State()
    # photo_geo task — two-step: first photo, then location
    waiting_for_photo_geo_photo    = State()
    waiting_for_photo_geo_location = State()


# ── Internal helpers ──────────────────────────────────────────────────────

def _extract_ids(data: dict) -> tuple[int, int]:
    """Return (checklist_id, item_id) from FSM state data."""
    return int(data["checklist_id"]), int(data["item_id"])


async def _complete_item(telegram_id: int, checklist_id: int, item_id: int, note: str) -> None:
    """Toggle item as completed via the backend, with the note as the answer."""
    await toggle_item(telegram_id, checklist_id, item_id, note=note)


async def _download_photo_bytes(bot: Bot, file_id: str, lang: str, message: Message) -> bytes | None:
    """
    Download a Telegram photo by file_id.
    Returns raw bytes on success, or None after sending an error reply
    (size too large, download failure).
    """
    file = await bot.get_file(file_id)
    size = file.file_size or 0
    if size > _MAX_PHOTO_BYTES:
        mb = size / (1024 * 1024)
        await message.answer(t("photo_too_large", lang, size_mb=f"{mb:.1f}"))
        return None
    buf = await bot.download_file(file.file_path)
    return buf.read()


# ── Entry points (called from checklists._advance_checklist) ──────────────

async def prompt_number(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Show a numeric input prompt and enter the waiting_for_number_input state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_number_input)
    await message.answer(t("ask_number", lang))


async def prompt_temperature(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Show a temperature input prompt and enter the waiting_for_temperature_input state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_temperature_input)
    await message.answer(t("ask_temperature", lang))


async def prompt_text(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Show a free-text input prompt and enter the waiting_for_text_input state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_text_input)
    await message.answer(t("ask_text", lang))


async def prompt_yes_no(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Show a yes/no inline keyboard and enter the waiting_for_yes_no state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_yes_no)
    await message.answer(t("ask_yes_no", lang), reply_markup=yes_no_keyboard(lang))


async def prompt_photo(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Ask the employee to send a photo and enter the waiting_for_photo_task state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_photo_task)
    await message.answer(t("ask_photo", lang))


async def prompt_photo_geo(
    message: Message,
    state: FSMContext,
    checklist_id: int,
    item_id: int,
    lang: str = "ru",
) -> None:
    """Ask the employee to send a photo (first step of photo_geo) and enter
    the waiting_for_photo_geo_photo state."""
    await state.update_data(checklist_id=checklist_id, item_id=item_id)
    await state.set_state(TaskInputStates.waiting_for_photo_geo_photo)
    await message.answer(t("ask_photo_geo", lang))


# ── Number handler ───────────────────────────────────────────────────────────

@router.message(TaskInputStates.waiting_for_number_input)
async def handle_number_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    raw = (message.text or "").strip().replace(",", ".")
    try:
        float(raw)  # validate
    except ValueError:
        await message.answer(t("invalid_number", lang))
        return

    try:
        await _complete_item(tid, checklist_id, item_id, note=raw)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang, state)


# ── Temperature handler ──────────────────────────────────────────────────────

_TEMP_MIN = -50.0
_TEMP_MAX = 200.0


@router.message(TaskInputStates.waiting_for_temperature_input)
async def handle_temperature_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    raw = (message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        await message.answer(t("invalid_temperature", lang))
        return

    if not (_TEMP_MIN <= val <= _TEMP_MAX):
        await message.answer(t("invalid_temperature", lang))
        return

    note = f"{val}\u00b0C"
    try:
        await _complete_item(tid, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang, state)


# ── Free-text handler ─────────────────────────────────────────────────────────

@router.message(TaskInputStates.waiting_for_text_input)
async def handle_text_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    note = (message.text or "").strip()
    if not note:
        await message.answer(t("ask_text", lang))
        return

    try:
        await _complete_item(tid, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang, state)


# ── Yes/No handler ────────────────────────────────────────────────────────────

@router.callback_query(
    TaskInputStates.waiting_for_yes_no,
    F.data.in_({"yes_no:yes", "yes_no:no"}),
)
async def handle_yes_no_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = callback.from_user.id
    lang = await get_employee_lang(tid)

    answer = "\u0414\u0430" if callback.data == "yes_no:yes" else "\u041d\u0435\u0442"

    try:
        await _complete_item(tid, checklist_id, item_id, note=answer)
    except ApiError as e:
        await callback.answer()
        assert callback.message is not None
        await callback.message.answer(t("save_error", lang, detail=e.detail))
        return

    await callback.answer()
    await state.clear()
    assert callback.message is not None
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(callback.message, checklist_id, tid, lang, state)


# ── Photo task handlers ───────────────────────────────────────────────────────

@router.message(TaskInputStates.waiting_for_photo_task, F.photo)
async def handle_photo_task(message: Message, state: FSMContext, bot: Bot) -> None:
    """Employee sent a photo for a 'photo' task type item."""
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    raw = await _download_photo_bytes(bot, message.photo[-1].file_id, lang, message)
    if raw is None:
        # _download_photo_bytes already sent an error message; stay in state
        return

    try:
        await upload_item_photo(tid, checklist_id, item_id, raw, "task_photo.jpg")
        await _complete_item(tid, checklist_id, item_id, note=t("photo_task_note", lang))
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang, state)


@router.message(TaskInputStates.waiting_for_photo_task)
async def handle_photo_task_wrong_input(message: Message, state: FSMContext) -> None:
    """Employee sent something other than a photo — re-prompt."""
    lang = await get_employee_lang(message.from_user.id)
    await message.answer(t("ask_photo_wrong_input", lang))


# ── Photo + geo task handlers (two-step flow) ─────────────────────────────────

@router.message(TaskInputStates.waiting_for_photo_geo_photo, F.photo)
async def handle_photo_geo_photo(message: Message, state: FSMContext) -> None:
    """First step: employee sent the photo. Store file_id and ask for location."""
    lang = await get_employee_lang(message.from_user.id)
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await state.set_state(TaskInputStates.waiting_for_photo_geo_location)
    await message.answer(t("ask_location", lang), reply_markup=skip_location_keyboard(lang))


@router.message(TaskInputStates.waiting_for_photo_geo_photo)
async def handle_photo_geo_photo_wrong_input(message: Message, state: FSMContext) -> None:
    """Employee sent something other than a photo in the photo_geo photo step — re-prompt."""
    lang = await get_employee_lang(message.from_user.id)
    await message.answer(t("ask_photo_wrong_input", lang))


@router.message(TaskInputStates.waiting_for_photo_geo_location, F.location)
async def handle_photo_geo_location(message: Message, state: FSMContext, bot: Bot) -> None:
    """Second step: employee sent their geolocation. Upload photo + save coords."""
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    file_id: str = data["photo_file_id"]
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    lat = message.location.latitude
    lon = message.location.longitude
    note = t("photo_geo_note", lang, lat=f"{lat:.6f}", lon=f"{lon:.6f}")

    raw = await _download_photo_bytes(bot, file_id, lang, message)
    if raw is None:
        await state.clear()
        return

    try:
        await upload_item_photo(tid, checklist_id, item_id, raw, "task_photo_geo.jpg")
        await _complete_item(tid, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang, state)


@router.callback_query(
    TaskInputStates.waiting_for_photo_geo_location,
    F.data == "photo_geo:skip_location",
)
async def handle_photo_geo_skip_location(
    callback: CallbackQuery, state: FSMContext, bot: Bot
) -> None:
    """Employee chose to skip the geolocation step. Upload photo without coords."""
    await callback.answer()
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    file_id: str = data["photo_file_id"]
    tid = callback.from_user.id
    lang = await get_employee_lang(tid)

    assert callback.message is not None
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    raw = await _download_photo_bytes(bot, file_id, lang, callback.message)
    if raw is None:
        await state.clear()
        return

    try:
        await upload_item_photo(tid, checklist_id, item_id, raw, "task_photo.jpg")
        await _complete_item(tid, checklist_id, item_id, note=t("photo_task_note", lang))
    except ApiError as e:
        await callback.message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await callback.message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(callback.message, checklist_id, tid, lang, state)
