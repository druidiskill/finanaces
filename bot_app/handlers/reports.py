from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_app.filters import AllowedUserFilter
from bot_app.keyboards import main_menu_keyboard


router = Router(name="reports")
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:reports")
async def reports_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📊 Раздел ОТЧЕТЫ пока не реализован.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
