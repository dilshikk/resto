from aiogram.fsm.state import State, StatesGroup


class LinkStates(StatesGroup):
    waiting_for_code = State()


class ItemStates(StatesGroup):
    waiting_for_problem_comment = State()
