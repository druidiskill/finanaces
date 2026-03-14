from aiogram.fsm.state import State, StatesGroup


class IncomeStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_confirmation = State()


class AdminStates(StatesGroup):
    waiting_for_const_value = State()
