"""
Bot internationalisation (i18n) module.

Supported languages
───────────────────
  ru  – Russian   (default, used when language is unknown or not mapped)
  uz  – Uzbek Latin
  en  – English   (fallback for all other Telegram UI languages)

Usage
─────
  from app.i18n import t, get_lang

  lang = get_lang(message.from_user.language_code)  # "ru" | "uz" | "en"
  await message.answer(t("welcome_linked", lang, name="Alice", role="Менеджер", branch="ТЦ Mall"))

Key guidelines
──────────────
  - Add new string keys to ALL three language dicts at the same time.
  - Keys in {curly braces} are named format placeholders; pass them as **kwargs.
  - If a key is missing in the requested language, Russian is used as the fallback.
  - The DEFAULT_LANG constant controls the last-resort fallback language.
"""

DEFAULT_LANG = "ru"

STRINGS: dict[str, dict[str, str]] = {
    # ────────────────────────── RUSSIAN ──────────────────────────
    "ru": {
        # ── Account linking (link.py) ──
        "welcome_linked": (
            "Здравствуйте, {name}! 👋\n\n"
            "Должность: {role}\n"
            "Филиал: {branch}\n\n"
            "Команда /today покажет ваши чек-листы на сегодня."
        ),
        "ask_for_code": (
            "Здравствуйте! 👋\n\n"
            "Чтобы начать, отправьте код приглашения от менеджера "
            "(8 символов, например ABC123XY)."
        ),
        "error_generic": "Произошла ошибка: {detail}",
        "ask_code_text": "Пожалуйста, отправьте код приглашения текстом.",
        "code_not_found": "Код приглашения не найден. Проверьте код и попробуйте снова.",
        "account_linked": (
            "Готово! Аккаунт привязан ✅\n\n"
            "Должность: {role}\n"
            "Филиал: {branch}\n\n"
            "Команда /today покажет ваши чек-листы на сегодня."
        ),
        "link_error": "Не удалось привязать аккаунт: {detail}",

        # ── Checklists (checklists.py) ──
        "step_header": "Шаг {current}/{total}",
        "standard_label": "Стандарт: {title}",
        "optional_item": "(необязательный пункт — можно пропустить)",
        "checklist_done": (
            "🎉 Все обязательные пункты выполнены!\n"
            "Менеджер сможет закрыть чек-лист в веб-панели."
        ),
        "not_linked": "Сначала привяжите аккаунт: отправьте /start и код приглашения.",
        "checklists_error": "Не удалось получить чек-листы: {detail}",
        "no_checklists": "На сегодня чек-листов нет. Загляните позже.",
        "checklists_today": "Ваши чек-листы на сегодня:",
        "item_done": "Отмечено ✅",
        "item_skipped": "Пропущено",
        "ask_problem": (
            "Опишите проблему коротко (можно прислать фото). "
            "Комментарий добавится в чек-лист."
        ),
        "problem_prefix": "⚠️ Проблема: {text}",
        "save_error": "Не удалось сохранить: {detail}",
        "problem_saved": "Записано! Пункт отмечен с комментарием о проблеме.",
        "problem_photo": "⚠️ Проблема (фото)",
        "photo_problem_saved": "Фото и отметка о проблеме сохранены.",
        "no_active_checklists": (
            "Нет активных чек-листов для прикрепления фото.\n"
            "Отправьте /today, чтобы увидеть список."
        ),
        "all_items_done": "Все пункты выполнены. Фото не прикреплено.",
        "photo_confirm": "Прикрепить фото к текущему пункту?\n\n\ud83d\udccb {template} \u2192 \u00ab{item}\u00bb",
        "photo_confirm_short": "Прикрепить фото к текущему пункту?\n\n\ud83d\udccb \u2192 \u00ab{item}\u00bb",
        "pick_checklist": "У вас несколько активных чек-листов. К какому прикрепить фото?",
        "no_pending_items": "В выбранном чек-листе нет невыполненных пунктов. Фото не прикреплено.",
        "photo_save_error": "Не удалось сохранить фото: {detail}",
        "photo_attached": "Фото прикреплено к пункту \u00ab{item}\u00bb ✅",
        "photo_cancelled": "Фото отменено. Отправьте /today, чтобы продолжить работу.",
        "detect_checklist_error": "Не удалось определить чек-лист: {detail}",
        "photo_too_large": "Фото слишком большое ({size_mb} МБ). Максимальный размер: 25 МБ.",

        # ── Bot command descriptions ──
        "cmd_start_desc": "Начать / привязать аккаунт",
        "cmd_today_desc": "Чек-листы на сегодня",
    },

    # ───────────────────────── UZBEK LATIN ─────────────────────────
    "uz": {
        "welcome_linked": (
            "Xush kelibsiz, {name}! 👋\n\n"
            "Lavozim: {role}\n"
            "Filial: {branch}\n\n"
            "/today buyrug'i bugungi chek-ro'yxatlaringizni ko'rsatadi."
        ),
        "ask_for_code": (
            "Salom! 👋\n\n"
            "Boshlash uchun menejerdan olgan taklif kodini yuboring "
            "(8 belgi, masalan ABC123XY)."
        ),
        "error_generic": "Xato yuz berdi: {detail}",
        "ask_code_text": "Iltimos, taklif kodini matn ko'rinishida yuboring.",
        "code_not_found": "Taklif kodi topilmadi. Kodni tekshirib, qayta urinib ko'ring.",
        "account_linked": (
            "Tayyor! Hisob bog'landi ✅\n\n"
            "Lavozim: {role}\n"
            "Filial: {branch}\n\n"
            "/today buyrug'i bugungi chek-ro'yxatlaringizni ko'rsatadi."
        ),
        "link_error": "Hisobni bog'lashda xato: {detail}",
        "step_header": "{current}/{total}-qadam",
        "standard_label": "Standart: {title}",
        "optional_item": "(ixtiyoriy band — o'tkazib yuborish mumkin)",
        "checklist_done": (
            "🎉 Barcha majburiy bandlar bajarildi!\n"
            "Menejer veb-panelda chek-ro'yxatni yopishi mumkin."
        ),
        "not_linked": "Avval hisobingizni bog'lang: /start yuboring va taklif kodini kiriting.",
        "checklists_error": "Chek-ro'yxatlarni olishda xato: {detail}",
        "no_checklists": "Bugun chek-ro'yxatlar yo'q. Keyinroq qarang.",
        "checklists_today": "Bugungi chek-ro'yxatlaringiz:",
        "item_done": "Belgilandi ✅",
        "item_skipped": "O'tkazib yuborildi",
        "ask_problem": (
            "Muammoni qisqacha tasvirlab bering (rasm ham yuborishingiz mumkin). "
            "Izoh chek-ro'yxatga qo'shiladi."
        ),
        "problem_prefix": "⚠️ Muammo: {text}",
        "save_error": "Saqlashda xato: {detail}",
        "problem_saved": "Saqlandi! Band muammo izohi bilan belgilandi.",
        "problem_photo": "⚠️ Muammo (rasm)",
        "photo_problem_saved": "Rasm va muammo belgisi saqlandi.",
        "no_active_checklists": (
            "Rasm biriktirish uchun faol chek-ro'yxatlar yo'q.\n"
            "/today buyrug'ini yuboring."
        ),
        "all_items_done": "Barcha bandlar bajarilgan. Rasm biriktirilmadi.",
        "photo_confirm": "Rasmni bandga biriktirish?\n\n\ud83d\udccb {template} \u2192 \u00ab{item}\u00bb",
        "photo_confirm_short": "Rasmni bandga biriktirish?\n\n\ud83d\udccb \u2192 \u00ab{item}\u00bb",
        "pick_checklist": "Bir nechta faol chek-ro'yxat bor. Qaysi biriga rasm biriktirish?",
        "no_pending_items": "Tanlangan chek-ro'yxatda bajarilmagan bandlar yo'q. Rasm biriktirilmadi.",
        "photo_save_error": "Rasmni saqlashda xato: {detail}",
        "photo_attached": "Rasm \u00ab{item}\u00bb bandiga biriktirildi ✅",
        "photo_cancelled": "Rasm bekor qilindi. Davom etish uchun /today yuboring.",
        "detect_checklist_error": "Chek-ro'yxatni aniqlab bo'lmadi: {detail}",
        "photo_too_large": "Rasm juda katta ({size_mb}\u00a0MB). Maksimal hajm: 25\u00a0MB.",
        "cmd_start_desc": "Boshlash / hisobni bog'lash",
        "cmd_today_desc": "Bugungi chek-ro'yxatlar",
    },

    # ───────────────────────── ENGLISH ──────────────────────────
    "en": {
        "welcome_linked": (
            "Hello, {name}! 👋\n\n"
            "Position: {role}\n"
            "Branch: {branch}\n\n"
            "Use /today to see your checklists for today."
        ),
        "ask_for_code": (
            "Hello! 👋\n\n"
            "To get started, send your invite code from the manager "
            "(8 characters, e.g. ABC123XY)."
        ),
        "error_generic": "An error occurred: {detail}",
        "ask_code_text": "Please send the invite code as text.",
        "code_not_found": "Invite code not found. Check the code and try again.",
        "account_linked": (
            "Done! Account linked ✅\n\n"
            "Position: {role}\n"
            "Branch: {branch}\n\n"
            "Use /today to see your checklists."
        ),
        "link_error": "Could not link account: {detail}",
        "step_header": "Step {current}/{total}",
        "standard_label": "Standard: {title}",
        "optional_item": "(optional — can be skipped)",
        "checklist_done": (
            "🎉 All required items completed!\n"
            "The manager can close the checklist in the web panel."
        ),
        "not_linked": "Please link your account first: send /start and your invite code.",
        "checklists_error": "Could not load checklists: {detail}",
        "no_checklists": "No checklists for today. Check back later.",
        "checklists_today": "Your checklists for today:",
        "item_done": "Marked ✅",
        "item_skipped": "Skipped",
        "ask_problem": (
            "Briefly describe the problem (you can also send a photo). "
            "It will be added as a comment."
        ),
        "problem_prefix": "⚠️ Problem: {text}",
        "save_error": "Could not save: {detail}",
        "problem_saved": "Saved! Item marked with a problem comment.",
        "problem_photo": "⚠️ Problem (photo)",
        "photo_problem_saved": "Photo and problem note saved.",
        "no_active_checklists": (
            "No active checklists to attach a photo to.\n"
            "Send /today to see the list."
        ),
        "all_items_done": "All items completed. Photo not attached.",
        "photo_confirm": "Attach photo to this item?\n\n\ud83d\udccb {template} \u2192 \u00ab{item}\u00bb",
        "photo_confirm_short": "Attach photo to this item?\n\n\ud83d\udccb \u2192 \u00ab{item}\u00bb",
        "pick_checklist": "You have several active checklists. Which one should the photo go to?",
        "no_pending_items": "The selected checklist has no pending items. Photo not attached.",
        "photo_save_error": "Could not save photo: {detail}",
        "photo_attached": "Photo attached to \u00ab{item}\u00bb ✅",
        "photo_cancelled": "Photo cancelled. Send /today to continue.",
        "detect_checklist_error": "Could not detect checklist: {detail}",
        "photo_too_large": "Photo is too large ({size_mb}\u00a0MB). Maximum size: 25\u00a0MB.",
        "cmd_start_desc": "Start / link account",
        "cmd_today_desc": "Today's checklists",
    },
}


def get_lang(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LANG
    lc = language_code.lower()
    if lc.startswith("uz"):
        return "uz"
    if lc.startswith("en"):
        return "en"
    return DEFAULT_LANG


def t(key: str, lang: str, **kwargs: object) -> str:
    lang_data = STRINGS.get(lang, {})
    template = lang_data.get(key) or STRINGS[DEFAULT_LANG].get(key, key)
    return template.format(**kwargs) if kwargs else template
