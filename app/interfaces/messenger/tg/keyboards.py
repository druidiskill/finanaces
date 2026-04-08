from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.interfaces.messenger.tg.constants import CONST_LABELS
from app.interfaces.messenger.tg.services import database


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 ДОХОДЫ", callback_data="menu:income")
    builder.button(text="💸 РАСХОДЫ", callback_data="menu:expenses")
    builder.button(text="📊 ОТЧЁТЫ", callback_data="menu:reports")
    builder.button(text="🧾 Задачи", callback_data="menu:tasks")
    builder.button(text="⚙️ Админ-панель", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def income_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Облагается налогом", callback_data="income:taxable")
    builder.button(text="✅ Не облагается налогом", callback_data="income:non_taxable")
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def taxable_source_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 От физ. лиц", callback_data="income:source:physical")
    builder.button(text="🏢 От юр. лиц", callback_data="income:source:legal")
    builder.button(text="⬅️ Назад", callback_data="menu:income")
    builder.adjust(1)
    return builder.as_markup()


def non_taxable_source_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 Наличные", callback_data="income:source:cash")
    builder.button(text="🏦 Безналичные", callback_data="income:source:cashless")
    builder.button(text="⬅️ Назад", callback_data="menu:income")
    builder.adjust(1)
    return builder.as_markup()


def wallet_keyboard(*, back_callback: str, wallet_ids: set[int] | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wallet in database.wallets.list_all():
        if wallet.ID is None:
            continue
        if wallet_ids is not None and wallet.ID not in wallet_ids:
            continue
        builder.button(
            text=f"👛 {wallet.name} ({wallet.summ:.2f})",
            callback_data=f"income:wallet:{wallet.ID}",
        )
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def destination_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍🏫 Учителя", callback_data="income:destination:teachers")
    builder.button(text="👤 Личные", callback_data="income:destination:personal")
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="income:confirm")
    builder.button(text="❌ Отмена", callback_data="income:cancel")
    builder.adjust(1)
    return builder.as_markup()


def expenses_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📌 Фиксированные", callback_data="expenses:section:fixes")
    builder.button(text="🔁 Постоянные", callback_data="expenses:section:needen")
    builder.button(text="🗂️ Прошлое / Будущее", callback_data="expenses:section:past_last")
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def reports_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сегодня", callback_data="reports:today")
    builder.button(text="👛 Кошельки", callback_data="reports:wallets")
    builder.button(text="📌 Фиксированные", callback_data="reports:fixes")
    builder.button(text="🔁 Постоянные", callback_data="reports:needen")
    builder.button(text="🔄 Переводы", callback_data="reports:transfers")
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def expense_categories_keyboard(*, section: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in database.list_expense_categories(section):
        builder.button(text=item.name, callback_data=f"expenses:category:{section}:{item.ID}")
    builder.button(text="⬅️ Назад", callback_data="menu:expenses")
    builder.adjust(1)
    return builder.as_markup()


def expense_wallet_keyboard(*, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wallet in database.wallets.list_all():
        if wallet.ID is None:
            continue
        builder.button(
            text=f"👛 {wallet.name} ({wallet.summ:.2f})",
            callback_data=f"expenses:wallet:{wallet.ID}",
        )
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def expense_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="expenses:confirm")
    builder.button(text="❌ Отмена", callback_data="expenses:cancel")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧮 Константы", callback_data="admin:const")
    builder.button(text="🗂️ Категории", callback_data="admin:categories")
    builder.button(text="📜 Последние операции", callback_data="admin:history")
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def const_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in CONST_LABELS.items():
        const_value = database.const.get_required(key)
        builder.button(
            text=f"✏️ {label}: {const_value.value:g}%",
            callback_data=f"admin:const:{key}",
        )
    builder.button(text="⬅️ Назад", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_sections_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📌 Фиксированные", callback_data="admin:categories:section:fixes")
    builder.button(text="🔁 Постоянные", callback_data="admin:categories:section:needen")
    builder.button(text="🗂️ Прошлое / Будущее", callback_data="admin:categories:section:past_last")
    builder.button(text="⬅️ Назад", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def admin_categories_keyboard(*, section: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in database.list_admin_categories(section):
        if item.ID is None:
            continue
        builder.button(text=item.name, callback_data=f"admin:categories:item:{section}:{item.ID}")
    builder.button(text="➕ Добавить категорию", callback_data=f"admin:categories:add:{section}")
    builder.button(text="⬅️ Назад", callback_data="admin:categories")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_fields_keyboard(*, section: str, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field_name, label in database.get_admin_category_field_labels(section).items():
        builder.button(
            text=label,
            callback_data=f"admin:categories:field:{section}:{category_id}:{field_name}",
        )
    builder.button(text="⬅️ Назад", callback_data=f"admin:categories:section:{section}")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_wallet_keyboard(*, section: str, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wallet in database.list_admin_wallets():
        if wallet.ID is None:
            continue
        builder.button(
            text=f"👛 {wallet.name} ({wallet.summ:.2f})",
            callback_data=f"admin:categories:wallet:{section}:{category_id}:{wallet.ID}",
        )
    builder.button(text="⬅️ Назад", callback_data=f"admin:categories:item:{section}:{category_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_parent_keyboard(*, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Без родителя", callback_data=f"admin:categories:parent:{category_id}:none")
    for item in database.list_past_last_parent_candidates(category_id):
        if item.ID is None:
            continue
        builder.button(text=item.name, callback_data=f"admin:categories:parent:{category_id}:{item.ID}")
    builder.button(text="⬅️ Назад", callback_data=f"admin:categories:item:past_last:{category_id}")
    builder.adjust(1)
    return builder.as_markup()


def tasks_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    wallet_map = database.get_wallet_map()
    for task in database.transfer_tasks.list_pending():
        if task.id is None:
            continue
        from_wallet = wallet_map.get(task.from_wallet_id)
        to_wallet = wallet_map.get(task.to_wallet_id)
        from_name = from_wallet.name if from_wallet else f"#{task.from_wallet_id}"
        to_name = to_wallet.name if to_wallet else f"#{task.to_wallet_id}"
        builder.button(
            text=f"{from_name} -> {to_name}: {task.amount:.2f}",
            callback_data=f"tasks:view:{task.id}",
        )
    builder.button(text="⬅️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить выполнение", callback_data=f"tasks:complete:{task_id}")
    builder.button(text="✏️ Изменить задачу", callback_data=f"tasks:edit:{task_id}")
    builder.button(text="⬅️ Назад", callback_data="menu:tasks")
    builder.adjust(1)
    return builder.as_markup()


def task_edit_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 Изменить сумму", callback_data=f"tasks:edit_amount:{task_id}")
    builder.button(text="👛 Изменить откуда", callback_data=f"tasks:edit_from:{task_id}")
    builder.button(text="🎯 Изменить куда", callback_data=f"tasks:edit_to:{task_id}")
    builder.button(text="⬅️ Назад", callback_data=f"tasks:view:{task_id}")
    builder.adjust(1)
    return builder.as_markup()


def task_wallet_select_keyboard(*, task_id: int, field: str, exclude_wallet_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for wallet in database.wallets.list_all():
        if wallet.ID is None:
            continue
        if exclude_wallet_id is not None and wallet.ID == exclude_wallet_id:
            continue
        builder.button(
            text=f"👛 {wallet.name} ({wallet.summ:.2f})",
            callback_data=f"tasks:set_wallet:{field}:{task_id}:{wallet.ID}",
        )
    builder.button(text="⬅️ Назад", callback_data=f"tasks:edit:{task_id}")
    builder.adjust(1)
    return builder.as_markup()


def single_action_keyboard(text: str, callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback_data)
    return builder.as_markup()

