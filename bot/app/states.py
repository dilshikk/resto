from aiogram.fsm.state import State, StatesGroup


class LinkStates(StatesGroup):
    waiting_for_code = State()


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
