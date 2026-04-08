from aiogram import F, Router
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.interfaces.messenger.tg.filters import AllowedUserFilter
from app.interfaces.messenger.tg.keyboards import (
    expense_categories_keyboard,
    expense_confirmation_keyboard,
    expense_wallet_keyboard,
    expenses_menu_keyboard,
    main_menu_keyboard,
    single_action_keyboard,
)
from app.interfaces.messenger.tg.services import database
from app.interfaces.messenger.tg.states import ExpenseStates
from app.interfaces.messenger.tg.utils import build_financial_overview_text


SECTION_LABELS = {
    "fixes": "Фиксированные",
    "needen": "Постоянные",
    "past_last": "Прошлое / Будущее",
}


router = Router(name="expenses")
router.message.filter(AllowedUserFilter())
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:expenses")
async def expenses_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "💸 РАСХОДЫ\nВыберите раздел:",
        reply_markup=expenses_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expenses:section:"))
async def expenses_section_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    section = callback.data.rsplit(":", 1)[-1]
    await callback.message.edit_text(
        f"💸 РАСХОДЫ -> {SECTION_LABELS[section]}\nВыберите категорию:",
        reply_markup=expense_categories_keyboard(section=section),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expenses:category:"))
async def expense_category_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, section, category_id = callback.data.split(":")
    category_id_int = int(category_id)
    categories = {item.ID: item for item in database.list_expense_categories(section) if item.ID is not None}
    category = categories.get(category_id_int)
    if category is None:
        await callback.answer("Категория не найдена")
        return

    await state.update_data(expense_section=section, expense_category_id=category_id_int, expense_category_name=category.name)
    await state.set_state(ExpenseStates.waiting_for_amount)
    await callback.message.edit_text(
        f"💸 {SECTION_LABELS[section]} -> {category.name}\n"
        f"Накоплено: {category.summ_now:.2f}\n"
        "Введите сумму расхода:",
        reply_markup=single_action_keyboard("⬅️ Назад", f"expenses:category:{section}:{category_id_int}"),
    )
    await callback.answer()


@router.message(ExpenseStates.waiting_for_amount)
async def expense_amount_handler(message: Message, state: FSMContext) -> None:
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = abs(float(raw_amount))
    except ValueError:
        await message.answer("⚠️ Введите сумму числом. Например: 1250.50")
        return

    if amount == 0:
        await message.answer("⚠️ Сумма расхода должна быть больше нуля.")
        return

    await state.update_data(expense_amount=amount)
    await state.set_state(ExpenseStates.waiting_for_wallet)
    await message.answer(
        "👛 Выберите кошелек оплаты:",
        reply_markup=expense_wallet_keyboard(back_callback="menu:expenses"),
    )


@router.callback_query(F.data.startswith("expenses:wallet:"), StateFilter(ExpenseStates.waiting_for_wallet))
async def expense_wallet_handler(callback: CallbackQuery, state: FSMContext) -> None:
    wallet_id = int(callback.data.rsplit(":", 1)[-1])
    wallet = database.wallets.get_by_id(wallet_id)
    if wallet is None:
        await callback.answer("Кошелек не найден")
        return

    data = await state.get_data()
    await state.update_data(expense_wallet_id=wallet_id, expense_wallet_name=wallet.name)
    await state.set_state(ExpenseStates.waiting_for_confirmation)
    await callback.message.edit_text(
        "Подтвердите расход:\n"
        f"Раздел: {SECTION_LABELS[data['expense_section']]}\n"
        f"Категория: {data['expense_category_name']}\n"
        f"Сумма: {data['expense_amount']:.2f}\n"
        f"Кошелек: {wallet.name}",
        reply_markup=expense_confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(StateFilter(ExpenseStates.waiting_for_confirmation), F.data == "expenses:confirm")
async def expense_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    result = database.create_expense_transaction(
        user_id=callback.from_user.id,
        section=data["expense_section"],
        category_id=data["expense_category_id"],
        wallet_id=data["expense_wallet_id"],
        amount=float(data["expense_amount"]),
    )
    transaction = result["transaction"]
    updated_category = result["updated_category"]
    updated_wallet = result["updated_wallet"]

    await state.clear()
    await callback.message.edit_text(
        "✅ Расход сохранен.\n"
        f"Раздел: {SECTION_LABELS[transaction.section]}\n"
        f"Категория: {transaction.category_name}\n"
        f"Сумма: {transaction.amount:.2f}\n"
        f"Кошелек: {updated_wallet.name}\n"
        f"Остаток в кошельке: {updated_wallet.summ:.2f}\n"
        f"Остаток в категории: {updated_category.summ_now:.2f}\n\n"
        f"{build_financial_overview_text()}",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "expenses:cancel")
async def expense_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        f"❌ Операция отменена.\n\n{build_financial_overview_text()}",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()

