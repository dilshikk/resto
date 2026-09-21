"""
Bot FSM handlers for non-checkbox task types.

Supported task types (beyond the default 'checkbox'):
  number      — employee enters a decimal number
  temperature — employee enters a decimal temperature value (°C)
  text        — employee types a free-text answer
  yes_no      — employee presses a Да/Нет inline-keyboard button

The flow for each type:
  1. The main checklists handler detects item.task_type != 'checkbox'
     and routes to the appropriate entry-point in this module.
  2. This module shows the prompt, stores (checklist_id, item_id) in FSM
     data, and sets the matching waiting_for_* state.
  3. On user response, this module validates the input, stores it as
     item.note via the backend toggle endpoint, and calls
     _advance_checklist() from the checklists handler to show the next item.

Incoming FSM data keys expected from the caller:
  checklist_id (int)  — active checklist ID
  item_id      (int)  — ID of the item being completed

All text responses fall back to Russian when the employee language is
unknown.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.api_client import ApiError, get_employee_lang, toggle_item
from app.i18n import t
from app.keyboards import yes_no_keyboard

router = Router(name="task_types")


# ── FSM States ────────────────────────────────────────────────────────────

class TaskInputStates(StatesGroup):
    waiting_for_number_input      = State()
    waiting_for_temperature_input = State()
    waiting_for_text_input        = State()
    waiting_for_yes_no            = State()


# ── Helpers ──────────────────────────────────────────────────────────────

def _extract_ids(data: dict) -> tuple[int, int]:
    """Return (checklist_id, item_id) from FSM state data."""
    return int(data["checklist_id"]), int(data["item_id"])


async def _complete_item(telegram_id: int, checklist_id: int, item_id: int, note: str) -> None:
    """Toggle item as completed via the backend, with the note as the answer."""
    await toggle_item(telegram_id, checklist_id, item_id, note=note)


# ── Entry points (called from checklists.py) ────────────────────────────────────

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

    # Advance to the next item — import here to avoid circular import
    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang)


# ── Temperature handler ──────────────────────────────────────────────────────

# Temperature valid range guard: -50 to +200 °C covers all restaurant contexts.
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

    note = f"{val}°C"
    try:
        await _complete_item(tid, checklist_id, item_id, note=note)
    except ApiError as e:
        await message.answer(t("save_error", lang, detail=e.detail))
        return

    await state.clear()
    await message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(message, checklist_id, tid, lang)


# ── Free-text handler ─────────────────────────────────────────────────────────

@router.message(TaskInputStates.waiting_for_text_input)
async def handle_text_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    checklist_id, item_id = _extract_ids(data)
    tid = message.from_user.id
    lang = await get_employee_lang(tid)

    note = (message.text or "").strip()
    if not note:
        # Re-prompt: empty answer not accepted
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
    await _advance_checklist(message, checklist_id, tid, lang)


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

    answer = "Да" if callback.data == "yes_no:yes" else "Нет"

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
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t("item_done", lang))

    from app.handlers.checklists import _advance_checklist
    await _advance_checklist(callback.message, checklist_id, tid, lang)
