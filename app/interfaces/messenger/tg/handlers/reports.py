from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.interfaces.messenger.tg.filters import AllowedUserFilter
from app.interfaces.messenger.tg.keyboards import reports_menu_keyboard
from app.interfaces.messenger.tg.utils import (
    build_fixes_report_text,
    build_needen_report_text,
    build_reports_transfers_text,
    build_today_report_text,
    build_wallets_report_text,
)


router = Router(name="reports")
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:reports")
async def reports_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📊 ОТЧЕТЫ\nВыберите отчет:",
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "reports:today")
async def reports_today_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        build_today_report_text(),
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "reports:wallets")
async def reports_wallets_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        build_wallets_report_text(),
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "reports:fixes")
async def reports_fixes_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        build_fixes_report_text(),
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "reports:needen")
async def reports_needen_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        build_needen_report_text(),
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "reports:transfers")
async def reports_transfers_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        build_reports_transfers_text(),
        reply_markup=reports_menu_keyboard(),
    )
    await callback.answer()

