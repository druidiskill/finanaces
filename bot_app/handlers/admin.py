from aiogram import F, Router
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot_app.constants import CONST_LABELS
from bot_app.filters import AdminUserFilter
from bot_app.keyboards import (
    admin_categories_keyboard,
    admin_category_fields_keyboard,
    admin_category_parent_keyboard,
    admin_category_sections_keyboard,
    admin_category_wallet_keyboard,
    admin_menu_keyboard,
    const_menu_keyboard,
    single_action_keyboard,
)
from bot_app.services import database
from bot_app.states import AdminStates
from database import DEFAULT_CONST_VALUES


router = Router(name="admin")
router.message.filter(AdminUserFilter())
router.callback_query.filter(AdminUserFilter())


ADMIN_SECTION_LABELS = {
    "fixes": "Фиксированные",
    "needen": "Постоянные",
    "past_last": "Прошлое / Будущее",
}


def _category_details_text(section: str, category_id: int) -> str:
    category = database.get_admin_category(section, category_id)
    if category is None:
        raise LookupError("Категория не найдена")
    details = []
    for field_name, label in database.get_admin_category_field_labels(section).items():
        details.append(f"{label}: {getattr(category, field_name)}")
    return f"🗂️ {ADMIN_SECTION_LABELS[section]} -> {category.name}\n" + "\n".join(details) + "\n\nВыберите поле:"


async def _show_category_card(callback: CallbackQuery, *, section: str, category_id: int) -> None:
    await callback.message.edit_text(
        _category_details_text(section, category_id),
        reply_markup=admin_category_fields_keyboard(section=section, category_id=category_id),
    )


@router.callback_query(F.data == "menu:admin")
async def admin_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("⚙️ Админ-панель", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:const")
async def admin_const_handler(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🧮 Константы распределения:", reply_markup=const_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:categories")
async def admin_categories_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🗂️ Изменение категорий\nВыберите раздел:",
        reply_markup=admin_category_sections_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:section:"))
async def admin_category_section_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    section = callback.data.rsplit(":", 1)[-1]
    await callback.message.edit_text(
        f"🗂️ {ADMIN_SECTION_LABELS[section]}\nВыберите категорию:",
        reply_markup=admin_categories_keyboard(section=section),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:add:"))
async def admin_category_add_handler(callback: CallbackQuery, state: FSMContext) -> None:
    section = callback.data.rsplit(":", 1)[-1]
    await state.set_state(AdminStates.waiting_for_new_category_name)
    await state.update_data(admin_new_category_section=section)
    await callback.message.edit_text(
        f"➕ {ADMIN_SECTION_LABELS[section]}\nВведите название новой категории:",
        reply_markup=single_action_keyboard("❌ Отмена", f"admin:categories:section:{section}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:item:"))
async def admin_category_item_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, _, section, category_id = callback.data.split(":")
    await state.clear()
    try:
        await _show_category_card(callback, section=section, category_id=int(category_id))
    except LookupError:
        await callback.answer("Категория не найдена")
        return
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:field:"))
async def admin_category_field_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, _, section, category_id, field_name = callback.data.split(":")
    category_id_int = int(category_id)
    category = database.get_admin_category(section, category_id_int)
    if category is None:
        await callback.answer("Категория не найдена")
        return

    if field_name == "wallet":
        await state.clear()
        await callback.message.edit_text(
            f"👛 {ADMIN_SECTION_LABELS[section]} -> {category.name}\nВыберите кошелек:",
            reply_markup=admin_category_wallet_keyboard(section=section, category_id=category_id_int),
        )
        await callback.answer()
        return

    if field_name == "parent_id" and section == "past_last":
        await state.clear()
        await callback.message.edit_text(
            f"🗂️ {ADMIN_SECTION_LABELS[section]} -> {category.name}\nВыберите родительскую категорию:",
            reply_markup=admin_category_parent_keyboard(category_id=category_id_int),
        )
        await callback.answer()
        return

    field_labels = database.get_admin_category_field_labels(section)
    await state.set_state(AdminStates.waiting_for_category_value)
    await state.update_data(
        admin_category_section=section,
        admin_category_id=category_id_int,
        admin_category_field=field_name,
    )
    await callback.message.edit_text(
        f"✏️ {ADMIN_SECTION_LABELS[section]} -> {category.name}\n"
        f"Поле: {field_labels[field_name]}\n"
        f"Сейчас: {getattr(category, field_name)}\n"
        "Введите новое значение:",
        reply_markup=single_action_keyboard("❌ Отмена", f"admin:categories:item:{section}:{category_id_int}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:wallet:"))
async def admin_category_wallet_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, _, section, category_id, wallet_id = callback.data.split(":")
    category_id_int = int(category_id)
    wallet_id_int = int(wallet_id)
    wallet = database.wallets.get_by_id(wallet_id_int)
    if wallet is None:
        await callback.answer("Кошелек не найден")
        return

    updated = database.update_admin_category_field(
        section=section,
        category_id=category_id_int,
        field_name="wallet",
        raw_value=str(wallet_id_int),
    )
    database.history.create(
        user_id=callback.from_user.id,
        action_type="category_updated",
        payload={
            "section": section,
            "category_id": category_id_int,
            "field_name": "wallet",
            "value": wallet_id_int,
        },
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ {ADMIN_SECTION_LABELS[section]} -> {updated.name}\nКошелек: {wallet.name}",
        reply_markup=admin_category_fields_keyboard(section=section, category_id=category_id_int),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:categories:parent:"))
async def admin_category_parent_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, _, category_id, parent_id = callback.data.split(":")
    category_id_int = int(category_id)

    raw_value = "" if parent_id == "none" else parent_id
    updated = database.update_admin_category_field(
        section="past_last",
        category_id=category_id_int,
        field_name="parent_id",
        raw_value=raw_value,
    )
    parent_name = "Без родителя"
    if parent_id != "none":
        parent_item = database.get_admin_category("past_last", int(parent_id))
        parent_name = parent_item.name if parent_item is not None else f"ID {parent_id}"

    database.history.create(
        user_id=callback.from_user.id,
        action_type="category_updated",
        payload={
            "section": "past_last",
            "category_id": category_id_int,
            "field_name": "parent_id",
            "value": None if parent_id == "none" else int(parent_id),
        },
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Прошлое / Будущее -> {updated.name}\nРодитель: {parent_name}",
        reply_markup=admin_category_fields_keyboard(section="past_last", category_id=category_id_int),
    )
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


@router.message(StateFilter(AdminStates.waiting_for_const_value))
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


@router.message(StateFilter(AdminStates.waiting_for_new_category_name))
async def admin_category_name_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    section = data["admin_new_category_section"]

    try:
        created = database.create_admin_category(section=section, name=message.text or "")
    except ValueError as error:
        await message.answer(f"⚠️ {error}")
        return

    database.history.create(
        user_id=message.from_user.id,
        action_type="category_created",
        payload={
            "section": section,
            "category_id": created.ID,
            "name": created.name,
        },
    )
    await state.clear()
    await message.answer(
        f"✅ {ADMIN_SECTION_LABELS[section]} -> {created.name}\nКатегория создана.",
        reply_markup=admin_category_fields_keyboard(section=section, category_id=created.ID or 0),
    )


@router.message(StateFilter(AdminStates.waiting_for_category_value))
async def admin_category_value_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    section = data["admin_category_section"]
    category_id = data["admin_category_id"]
    field_name = data["admin_category_field"]
    field_label = database.get_admin_category_field_labels(section)[field_name]

    try:
        updated = database.update_admin_category_field(
            section=section,
            category_id=category_id,
            field_name=field_name,
            raw_value=message.text or "",
        )
    except ValueError as error:
        await message.answer(f"⚠️ {error}")
        return
    except LookupError as error:
        await state.clear()
        await message.answer(f"⚠️ {error}", reply_markup=admin_menu_keyboard())
        return

    database.history.create(
        user_id=message.from_user.id,
        action_type="category_updated",
        payload={
            "section": section,
            "category_id": category_id,
            "field_name": field_name,
            "value": getattr(updated, field_name),
        },
    )
    await state.clear()
    await message.answer(
        f"✅ {ADMIN_SECTION_LABELS[section]} -> {updated.name}\n{field_label}: {getattr(updated, field_name)}",
        reply_markup=admin_category_fields_keyboard(section=section, category_id=updated.ID or category_id),
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
