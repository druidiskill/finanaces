from aiogram.fsm.state import State, StatesGroup


class AddFlow(StatesGroup):
    waiting_amount = State()
    waiting_category_select = State()
    waiting_category_add = State()
    waiting_comment = State()


class SummaryFlow(StatesGroup):
    waiting_kind = State()
    waiting_period = State()
    waiting_range = State()
    waiting_category = State()


class GoalsFlow(StatesGroup):
    waiting_goal_title = State()
    waiting_goal_due = State()
    waiting_step_title = State()
    waiting_step_due = State()
    waiting_delegate_name = State()
    waiting_comment_text = State()
