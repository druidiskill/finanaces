from aiogram.fsm.state import State, StatesGroup


class IncomeStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_confirmation = State()


class ExpenseStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    waiting_for_confirmation = State()


class AdminStates(StatesGroup):
    waiting_for_const_value = State()
    waiting_for_category_value = State()
    waiting_for_new_category_name = State()


class TaskStates(StatesGroup):
    waiting_for_amount = State()

