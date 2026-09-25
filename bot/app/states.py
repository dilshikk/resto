from aiogram.fsm.state import State, StatesGroup


class LinkStates(StatesGroup):
    waiting_for_code = State()


class RegisterStates(StatesGroup):
    """
    Self-service registration flow, entered when /start is pressed by a
    telegram_id that GET /bot/status reports as "not_registered" (i.e. it
    has no invite code and has never messaged the bot before).
    """
    # First step: the employee picks the bot language (ru / uz / en).
    choosing_language = State()
    # Waiting for the employee to tap the "Share contact" reply-keyboard
    # button so we can capture their phone number.
    waiting_for_contact = State()


class ItemStates(StatesGroup):
    waiting_for_problem_comment = State()


class PhotoStates(StatesGroup):
    # User sent a standalone photo and has multiple active checklists:
    # waiting for them to pick which checklist the photo belongs to.
    waiting_for_checklist_choice = State()
    # Checklist is identified; waiting for explicit confirmation before upload.
    waiting_for_confirmation = State()


class ReauthStates(StatesGroup):
    # Bot restarted and lost the in-memory token cache; waiting for the
    # employee to re-confirm by sending /start so we can restore the token.
    waiting_for_reauth = State()
