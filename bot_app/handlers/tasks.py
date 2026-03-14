from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot_app.filters import AllowedUserFilter
from bot_app.keyboards import main_menu_keyboard
from bot_app.utils import build_tasks_text


router = Router(name="tasks")
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:tasks")
async def tasks_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        build_tasks_text(),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
