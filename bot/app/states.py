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
