from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_app.constants import CONST_LABELS
from bot_app.services import database


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 ДОХОДЫ", callback_data="menu:income")
    builder.button(text="💸 РАСХОДЫ", callback_data="menu:expenses")
    builder.button(text="📊 ОТЧЕТЫ", callback_data="menu:reports")
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


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧮 Константы", callback_data="admin:const")
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


def single_action_keyboard(text: str, callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback_data)
    return builder.as_markup()
