from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def yes_no_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """
    Inline keyboard with two buttons for yes_no task type items.

    Button labels are localised:
      ru: Да / Нет
      uz: Ha / Yo'q
      en: Yes / No

    Callback data is always 'yes_no:yes' or 'yes_no:no' regardless of
    language so the handler can compare a constant string.
    """
    from app.i18n import t

    yes_label = t("yes_btn", lang)
    no_label = t("no_btn", lang)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes_label, callback_data="yes_no:yes"),
                InlineKeyboardButton(text=no_label, callback_data="yes_no:no"),
            ]
        ]
    )
