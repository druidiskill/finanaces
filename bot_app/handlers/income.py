from __future__ import annotations

from aiogram import F, Router
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_app.constants import INCOME_DESTINATION_LABELS, INCOME_TAX_LABELS
from bot_app.filters import AllowedUserFilter
from bot_app.keyboards import (
    confirmation_keyboard,
    destination_keyboard,
    income_menu_keyboard,
    main_menu_keyboard,
    non_taxable_source_keyboard,
    single_action_keyboard,
    taxable_source_keyboard,
    wallet_keyboard,
)
from bot_app.services import database
from bot_app.states import IncomeStates
from bot_app.utils import build_financial_overview_text, format_distribution_preview


router = Router(name="income")
router.message.filter(AllowedUserFilter())
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:income")
async def income_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("💰 ДЕНЬГИ\nВыберите тип дохода:", reply_markup=income_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "income:taxable")
async def taxable_income_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_data({"tax_mode": "taxable"})
    await callback.message.edit_text(
        "🧾 Облагается налогом\nВыберите источник:",
        reply_markup=taxable_source_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "income:non_taxable")
async def non_taxable_income_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_data({"tax_mode": "non_taxable"})
    await callback.message.edit_text(
        "✅ Не облагается налогом\nВыберите тип поступления:",
        reply_markup=non_taxable_source_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("income:source:"))
async def income_source_handler(callback: CallbackQuery, state: FSMContext) -> None:
    source_type = callback.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    data["source_type"] = source_type
    await state.set_data(data)

    if data.get("tax_mode") == "non_taxable":
        await callback.message.edit_text(
            f"✅ Не облагается налогом -> {('💵 Наличные' if source_type == 'cash' else '🏦 Безналичные')}\nВыберите направление:",
            reply_markup=destination_keyboard("income:non_taxable"),
        )
        await callback.answer()
        return

    if source_type == "legal":
        await state.update_data(destination="personal")
        await callback.message.edit_text(
            "🧾 Облагается налогом -> 🏢 От юр. лиц\nВыберите кошелек получения:",
            reply_markup=wallet_keyboard(
                back_callback="menu:income",
                wallet_ids={wallet.ID for wallet in database.wallets.list_all() if wallet.ID not in {None, 1}},
            ),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🧾 Облагается налогом -> 👤 От физ. лиц\nВыберите направление:",
        reply_markup=destination_keyboard("income:taxable"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("income:destination:"))
async def income_destination_handler(callback: CallbackQuery, state: FSMContext) -> None:
    destination = callback.data.rsplit(":", 1)[-1]
    data = await state.get_data()
    tax_mode = data.get("tax_mode", "non_taxable")
    source_type = data.get("source_type", "none")

    await state.update_data(destination=destination, source_type=source_type)
    await state.set_state(IncomeStates.waiting_for_amount)

    prefix = INCOME_TAX_LABELS[tax_mode]
    if tax_mode == "taxable" and source_type == "physical":
        prefix += " -> От физ. лиц"
    if tax_mode == "non_taxable":
        source_label = "Наличные" if source_type == "cash" else "Безналичные"
        prefix += f" -> {source_label}"
        if source_type == "cash":
            await state.update_data(wallet_id=1)
            await state.set_state(IncomeStates.waiting_for_amount)
            await callback.message.edit_text(
                f"{prefix} -> {INCOME_DESTINATION_LABELS[destination]}\nВведите сумму дохода:",
                reply_markup=single_action_keyboard("❌ Отмена", "menu:income"),
            )
            await callback.answer()
            return

    await callback.message.edit_text(
        f"{prefix} -> {INCOME_DESTINATION_LABELS[destination]}\nВыберите кошелек получения:",
        reply_markup=wallet_keyboard(
            back_callback="menu:income",
            wallet_ids=(
                {wallet.ID for wallet in database.wallets.list_all() if wallet.ID not in {None, 1}}
                if source_type in {"cashless", "physical", "legal", "none"}
                else None
            ),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("income:wallet:"))
async def income_wallet_handler(callback: CallbackQuery, state: FSMContext) -> None:
    wallet_id = int(callback.data.rsplit(":", 1)[-1])
    await state.update_data(wallet_id=wallet_id)
    await state.set_state(IncomeStates.waiting_for_amount)
    await callback.message.edit_text(
        "💵 Введите сумму дохода:",
        reply_markup=single_action_keyboard("❌ Отмена", "menu:income"),
    )
    await callback.answer()


@router.message(IncomeStates.waiting_for_amount)
async def income_amount_handler(message: Message, state: FSMContext) -> None:
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer("⚠️ Введите сумму числом. Например: 12500.50")
        return

    if amount <= 0:
        await message.answer("⚠️ Сумма должна быть больше нуля.")
        return

    data = await state.get_data()
    distribution = database.calculate_income_distribution(
        amount=amount,
        tax_mode=data["tax_mode"],
        source_type=data["source_type"],
        destination=data["destination"],
    )
    await state.update_data(amount=amount, distribution=distribution)
    await state.set_state(IncomeStates.waiting_for_confirmation)
    preview_data = await state.get_data()

    await message.answer(
        format_distribution_preview(preview_data, distribution),
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(StateFilter(IncomeStates.waiting_for_confirmation), F.data == "income:confirm")
async def income_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    result = database.create_income_transaction(
        user_id=callback.from_user.id,
        wallet_id=data.get("wallet_id"),
        tax_mode=data["tax_mode"],
        source_type=data["source_type"],
        destination=data["destination"],
        amount=float(data["amount"]),
    )
    transaction = result["transaction"]
    fix_allocation = result["fix_allocation"]
    needen_allocation = result["needen_allocation"]
    past_last_allocation = result["past_last_allocation"]
    totals = database.get_day_totals()
    wallet_map = database.get_wallet_map()
    income_wallet = wallet_map.get(transaction.wallet_id) if transaction.wallet_id is not None else None
    legal_tax_lines = []
    for index, item in enumerate(totals["legal_taxes_items"], start=1):
        legal_tax_lines.append(f"{index}) {item['taxes_amount']:.2f}")
    legal_taxes_text = "\n".join(legal_tax_lines) if legal_tax_lines else "нет"
    allocation_text = ""
    if fix_allocation["allocations"]:
        allocation_lines = [f"📌 В отложенные платежи: {fix_allocation['allocated_amount']:.2f}"]
        for index, allocation in enumerate(fix_allocation["allocations"], start=1):
            target_wallet = wallet_map.get(allocation["fix"].wallet)
            target_wallet_name = target_wallet.name if target_wallet else f"#{allocation['fix'].wallet}"
            transfer_suffix = ""
            if allocation["transfer_required"] and income_wallet is not None:
                transfer_suffix = f" | перевод: {income_wallet.name} -> {target_wallet_name}"
            allocation_lines.append(
                f"{index}) {allocation['fix'].name}: "
                f"+{allocation['allocated_amount']:.2f} "
                f"(накоплено {allocation['fix'].summ_now:.2f} / {allocation['fix'].summ_fix:.2f}, "
                f"хранение: {target_wallet_name}){transfer_suffix}"
            )
        allocation_text = "\n" + "\n".join(allocation_lines)

    needen_text = ""
    if needen_allocation["allocations"]:
        grouped_needen_allocations: dict[int, dict[str, object]] = {}
        for allocation in needen_allocation["allocations"]:
            needen = allocation["needen"]
            needen_id = needen.ID
            if needen_id is None:
                continue
            if needen_id not in grouped_needen_allocations:
                grouped_needen_allocations[needen_id] = {
                    "needen": needen,
                    "allocated_amount": 0.0,
                    "transfer_required": False,
                }
            grouped_needen_allocations[needen_id]["allocated_amount"] = round(
                float(grouped_needen_allocations[needen_id]["allocated_amount"]) + allocation["allocated_amount"],
                2,
            )
            grouped_needen_allocations[needen_id]["needen"] = needen
            grouped_needen_allocations[needen_id]["transfer_required"] = (
                bool(grouped_needen_allocations[needen_id]["transfer_required"]) or allocation["transfer_required"]
            )

        needen_lines = [f"🧺 В needen: {needen_allocation['allocated_amount']:.2f}"]
        for index, grouped in enumerate(grouped_needen_allocations.values(), start=1):
            needen = grouped["needen"]
            target_wallet = wallet_map.get(needen.wallet)
            target_wallet_name = target_wallet.name if target_wallet else f"#{needen.wallet}"
            transfer_suffix = ""
            if grouped["transfer_required"] and income_wallet is not None:
                transfer_suffix = f" | перевод: {income_wallet.name} -> {target_wallet_name}"
            needen_lines.append(
                f"{index}) {needen.name}: "
                f"+{float(grouped['allocated_amount']):.2f} "
                f"(накоплено {needen.summ_now:.2f} / {needen.summ_need:.2f}, "
                f"хранение: {target_wallet_name}){transfer_suffix}"
            )
        needen_text = "\n" + "\n".join(needen_lines)

    past_last_text = ""
    if past_last_allocation["allocations"]:
        grouped_past_last_allocations: dict[int, dict[str, object]] = {}
        for allocation in past_last_allocation["allocations"]:
            past_last = allocation["past_last"]
            past_last_id = past_last.ID
            if past_last_id is None:
                continue
            if past_last_id not in grouped_past_last_allocations:
                grouped_past_last_allocations[past_last_id] = {
                    "past_last": past_last,
                    "allocated_amount": 0.0,
                    "transfer_required": False,
                    "weight": allocation["weight"],
                }
            grouped_past_last_allocations[past_last_id]["allocated_amount"] = round(
                float(grouped_past_last_allocations[past_last_id]["allocated_amount"]) + allocation["allocated_amount"],
                2,
            )
            grouped_past_last_allocations[past_last_id]["past_last"] = past_last
            grouped_past_last_allocations[past_last_id]["transfer_required"] = (
                bool(grouped_past_last_allocations[past_last_id]["transfer_required"]) or allocation["transfer_required"]
            )

        past_last_lines = [f"🗂️ В past/last: {past_last_allocation['allocated_amount']:.2f}"]
        for index, grouped in enumerate(grouped_past_last_allocations.values(), start=1):
            past_last = grouped["past_last"]
            target_wallet = wallet_map.get(past_last.wallet) if past_last.wallet is not None else None
            target_wallet_name = target_wallet.name if target_wallet else "не указан"
            transfer_suffix = ""
            if grouped["transfer_required"] and income_wallet is not None:
                transfer_suffix = f" | перевод: {income_wallet.name} -> {target_wallet_name}"
            past_last_lines.append(
                f"{index}) {past_last.name}: "
                f"+{float(grouped['allocated_amount']):.2f} "
                f"(накоплено {past_last.summ_now:.2f}, "
                f"доля {float(grouped['weight']) * 100:.2f}%, "
                f"хранение: {target_wallet_name}){transfer_suffix}"
            )
        past_last_text = "\n" + "\n".join(past_last_lines)

    await state.clear()
    await callback.message.edit_text(
        "✅ Доход сохранен.\n"
        f"👛 Кошелек: {income_wallet.name if income_wallet else 'не указан'}\n"
        f"Сумма: {transaction.amount:.2f}\n"
        f"Учителям: {transaction.teachers_amount:.2f}\n"
        f"Налоги: {transaction.taxes_amount:.2f}\n"
        f"Личные: {transaction.spendable_personal_amount:.2f}{allocation_text}{needen_text}{past_last_text}\n\n"
        f"📅 Итого за {totals['date']}:\n"
        f"💰 Доходы: {totals['income_total']:.2f}\n"
        f"👨‍🏫 Учителям: {totals['teachers_total']:.2f}\n"
        f"🧾 Налоги от физ. лиц: {totals['physical_taxes_total']:.2f}\n"
        f"🏢 Налоги от юр. лиц:\n{legal_taxes_text}\n"
        f"💸 Расходы: {totals['expense_total']:.2f}",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "income:cancel")
async def income_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        f"❌ Операция отменена.\n\n{build_financial_overview_text()}",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
