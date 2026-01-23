from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..helpers import delete_user_message, edit_or_answer
from ..keyboards import build_main_kb
from ..utils import is_allowed


async def start(message: Message):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    await message.answer("🔘 Выберите действие:", reply_markup=build_main_kb())
    await delete_user_message(message)


async def on_start(message: Message):
    await start(message)


async def on_section_finance(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    text = "💼 Учет доходов/расходов — выберите действие:"
    kb = InlineKeyboardBuilder()
    kb.button(text="➕💰 Добавить доход", callback_data="add_income")
    kb.button(text="➖💸 Добавить расход", callback_data="add_expense")
    kb.button(text="📊 Сводка", callback_data="summary")
    kb.button(text="🔙 Назад", callback_data="section_back")
    kb.adjust(1)
    await edit_or_answer(callback, text, reply_markup=kb.as_markup())
    await callback.answer()


async def on_section_back(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await edit_or_answer(callback, "🔘 Выберите действие:", reply_markup=build_main_kb())
    await callback.answer()


async def on_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_answer(callback, "❌ Отменено.", reply_markup=build_main_kb())
    await callback.answer()


def register_common(dp):
    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(on_section_finance, lambda c: c.data == "section_finance")
    dp.callback_query.register(on_section_back, lambda c: c.data == "section_back")
    dp.callback_query.register(on_cancel, lambda c: c.data == "cancel")
    dp.message.register(start, StateFilter(None))
