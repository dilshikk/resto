from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.i18n import t

# Shift labels per language
_SHIFT_LABELS: dict[str, dict[str, str]] = {
    "ru": {"morning": "Открытие", "afternoon": "Смена", "evening": "Закрытие"},
    "uz": {"morning": "Ochilish", "afternoon": "Smena", "evening": "Yopilish"},
    "en": {"morning": "Opening", "afternoon": "Shift", "evening": "Closing"},
}

# Button labels per language
_BTN: dict[str, dict[str, str]] = {
    "ru": {
        "done": "\u2705 Выполнено",
        "problem": "\u26a0\ufe0f Проблема",
        "skip": "\u23ed Пропустить",
        "back": "\u2b05\ufe0f К списку чек-листов",
        "cancel": "\u274c Отмена",
        "attach": "\u2705 Прикрепить к \u00ab{item}\u00bb",
    },
    "uz": {
        "done": "\u2705 Bajarildi",
        "problem": "\u26a0\ufe0f Muammo",
        "skip": "\u23ed O\u2019tkazib yuborish",
        "back": "\u2b05\ufe0f Chek-ro\u2019yxatlar",
        "cancel": "\u274c Bekor qilish",
        "attach": "\u2705 \u00ab{item}\u00bb bandiga biriktirish",
    },
    "en": {
        "done": "\u2705 Done",
        "problem": "\u26a0\ufe0f Problem",
        "skip": "\u23ed Skip",
        "back": "\u2b05\ufe0f Back to checklists",
        "cancel": "\u274c Cancel",
        "attach": "\u2705 Attach to \u00ab{item}\u00bb",
    },
}

# Shown before the user has chosen a language, so it is bilingual.
CHOOSE_LANGUAGE_TEXT = "Выберите язык / Tilni tanlang"


def _shift_label(shift: str, lang: str) -> str:
    return _SHIFT_LABELS.get(lang, _SHIFT_LABELS["ru"]).get(shift, shift)


def _btn(key: str, lang: str, **kwargs: str) -> str:
    labels = _BTN.get(lang, _BTN["ru"])
    template = labels.get(key, _BTN["ru"].get(key, key))
    return template.format(**kwargs) if kwargs else template


# ── Language selection ────────────────────────────────────────────────────

def language_keyboard() -> InlineKeyboardMarkup:
    """Callback data: 'lang:ru' | 'lang:uz'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f1f7\U0001f1fa Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="\U0001f1fa\U0001f1ff O\u2018zbekcha", callback_data="lang:uz"),
            ],
        ]
    )


# ── Checklist navigation ──────────────────────────────────────────────────

def checklists_keyboard(checklists: list[dict], lang: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    for cl in checklists:
        label = _shift_label(cl["shift"], lang)
        progress = f"{cl['completed_items']}/{cl['total_items']}"
        status_icon = "\u2705" if cl["status"] == "completed" else "\U0001f552"
        text = f"{status_icon} {cl['template_name']} ({label}) \u2014 {progress}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"cl:{cl['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_keyboard(
    checklist_id: int,
    item_id: int,
    *,
    is_required: bool,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_btn("done", lang), callback_data=f"done:{checklist_id}:{item_id}")],
        [InlineKeyboardButton(text=_btn("problem", lang), callback_data=f"problem:{checklist_id}:{item_id}")],
    ]
    if not is_required:
        rows.append([InlineKeyboardButton(text=_btn("skip", lang), callback_data=f"skip:{checklist_id}:{item_id}")])
    rows.append([InlineKeyboardButton(text=_btn("back", lang), callback_data="back:checklists")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_list_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=_btn("back", lang), callback_data="back:checklists")]]
    )


# ── Standalone photo flow ─────────────────────────────────────────────────

def photo_checklist_keyboard(checklists: list[dict], lang: str = "ru") -> InlineKeyboardMarkup:
    """
    Shown when the user sends a standalone photo but has several active
    checklists — lets them pick the exact one the photo belongs to.
    """
    rows = []
    for cl in checklists:
        label = _shift_label(cl["shift"], lang)
        text = f"\U0001f4cb {cl['template_name']} ({label})"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"photo_cl:{cl['id']}")])
    rows.append([InlineKeyboardButton(text=_btn("cancel", lang), callback_data="photo_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def photo_confirm_keyboard(
    checklist_id: int, item_title: str, lang: str = "ru"
) -> InlineKeyboardMarkup:
    """
    Confirmation step: shows the target item name and asks the user to
    approve before the photo is actually uploaded.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=_btn("attach", lang, item=item_title[:40]),
                callback_data=f"photo_confirm:{checklist_id}",
            )],
            [InlineKeyboardButton(text=_btn("cancel", lang), callback_data="photo_cancel")],
        ]
    )


# ── Task-type keyboards ───────────────────────────────────────────────────

def yes_no_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """
    Inline keyboard with two buttons for yes_no task type items.

    Callback data is always 'yes_no:yes' or 'yes_no:no' regardless of
    language so the handler can compare a constant string.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("yes_btn", lang), callback_data="yes_no:yes"),
                InlineKeyboardButton(text=t("no_btn", lang), callback_data="yes_no:no"),
            ]
        ]
    )


def skip_location_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """
    Single "Skip geolocation" button for photo_geo items: the photo is
    uploaded without coordinates.

    Callback data: 'photo_geo:skip_location'
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("skip_location_btn", lang),
                    callback_data="photo_geo:skip_location",
                )
            ]
        ]
    )


# ── Self-service registration ─────────────────────────────────────────────

def share_contact_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """
    Reply-keyboard with a single "Share contact" button using Telegram's
    native contact-request feature (request_contact=True).
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("share_contact_btn", lang), request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Hide the reply-keyboard once the contact has been shared."""
    return ReplyKeyboardRemove()
