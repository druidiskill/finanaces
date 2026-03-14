from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_app.constants import CONST_LABELS
from bot_app.filters import AdminUserFilter
from bot_app.keyboards import admin_menu_keyboard, const_menu_keyboard, single_action_keyboard
from bot_app.services import database
from bot_app.states import AdminStates
from database import DEFAULT_CONST_VALUES


router = Router(name="admin")
router.message.filter(AdminUserFilter())
router.callback_query.filter(AdminUserFilter())


@router.callback_query(F.data == "menu:admin")
async def admin_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("⚙️ Админ-панель", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:const")
async def admin_const_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🧮 Константы распределения:", reply_markup=const_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:const:"))
async def admin_const_edit_handler(callback: CallbackQuery, state: FSMContext) -> None:
    const_key = callback.data.split(":")[-1]
    await state.set_state(AdminStates.waiting_for_const_value)
    await state.update_data(const_key=const_key)
    await callback.message.edit_text(
        f"✏️ Введите новое значение для '{CONST_LABELS[const_key]}' в процентах:",
        reply_markup=single_action_keyboard("❌ Отмена", "menu:admin"),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_const_value)
async def admin_const_value_handler(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").replace(",", ".").strip()
    try:
        value = float(raw_value)
    except ValueError:
        await message.answer("⚠️ Введите число. Например: 60 или 4.5")
        return

    if value < 0 or value > 100:
        await message.answer("⚠️ Процент должен быть в диапазоне от 0 до 100.")
        return

    data = await state.get_data()
    const_key = data["const_key"]
    database.const.set(
        const_key,
        value,
        description=DEFAULT_CONST_VALUES.get(const_key, (value, ""))[1],
    )
    database.history.create(
        user_id=message.from_user.id,
        action_type="const_updated",
        payload={"key": const_key, "value": value},
    )
    await state.clear()
    await message.answer(
        f"✅ Константа '{CONST_LABELS[const_key]}' обновлена: {value:g}%",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:history")
async def admin_history_handler(callback: CallbackQuery) -> None:
    recent_transactions = database.income_transactions.list_recent(5)
    recent_history = database.history.list_recent(5)

    transaction_lines = ["📜 Последние операции доходов:"]
    if recent_transactions:
        for item in recent_transactions:
            transaction_lines.append(
                f"#{item.id} {item.amount:.2f} | учителям {item.teachers_amount:.2f} | "
                f"налоги {item.taxes_amount:.2f} | личные {item.personal_amount:.2f}"
            )
    else:
        transaction_lines.append("Нет записей.")

    history_lines = ["", "🕓 История действий:"]
    if recent_history:
        for item in recent_history:
            history_lines.append(f"#{item.id} {item.action_type} | user={item.user_id}")
    else:
        history_lines.append("Нет записей.")

    await callback.message.edit_text(
        "\n".join(transaction_lines + history_lines),
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()
