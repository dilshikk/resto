from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SHIFT_LABELS = {
    "morning": "Открытие",
    "afternoon": "Смена",
    "evening": "Закрытие",
}


def checklists_keyboard(checklists: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for cl in checklists:
        label = SHIFT_LABELS.get(cl["shift"], cl["shift"])
        progress = f"{cl['completed_items']}/{cl['total_items']}"
        status_icon = "✅" if cl["status"] == "completed" else "🕒"
        text = f"{status_icon} {cl['template_name']} ({label}) — {progress}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"cl:{cl['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_keyboard(checklist_id: int, item_id: int, *, is_required: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{checklist_id}:{item_id}")],
        [InlineKeyboardButton(text="⚠️ Проблема", callback_data=f"problem:{checklist_id}:{item_id}")],
    ]
    if not is_required:
        rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip:{checklist_id}:{item_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ К списку чек-листов", callback_data="back:checklists")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ К списку чек-листов", callback_data="back:checklists")]]
    )


def photo_checklist_keyboard(checklists: list[dict]) -> InlineKeyboardMarkup:
    """
    Shown when the user sends a standalone photo but has several active
    checklists — lets them pick the exact one the photo belongs to.
    """
    rows = []
    for cl in checklists:
        label = SHIFT_LABELS.get(cl["shift"], cl["shift"])
        text = f"📋 {cl['template_name']} ({label})"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"photo_cl:{cl['id']}")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="photo_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def photo_confirm_keyboard(checklist_id: int, item_title: str) -> InlineKeyboardMarkup:
    """
    Confirmation step: shows the target item name and asks the user to
    approve before the photo is actually uploaded.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Прикрепить к «{item_title[:40]}»",
                callback_data=f"photo_confirm:{checklist_id}",
            )],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="photo_cancel")],
        ]
    )
