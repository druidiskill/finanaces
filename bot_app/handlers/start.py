from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_app.filters import AllowedUserFilter
from bot_app.keyboards import main_menu_keyboard
from bot_app.utils import build_financial_overview_text


router = Router(name="start")
router.message.filter(AllowedUserFilter())
router.callback_query.filter(AllowedUserFilter())


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_financial_overview_text(), reply_markup=main_menu_keyboard())


@router.callback_query(lambda callback: callback.data == "menu:main")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(build_financial_overview_text(), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(StateFilter(None))
async def fallback_handler(message: Message, state: FSMContext) -> None:
    await message.answer(build_financial_overview_text(), reply_markup=main_menu_keyboard())
