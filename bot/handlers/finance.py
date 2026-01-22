import logging
from datetime import datetime
from decimal import Decimal

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..helpers import delete_user_message, edit_or_answer
from ..keyboards import build_cancel_kb, build_category_kb, build_comment_kb, build_main_kb
from ..sheets import append_row, load_categories_from_sheet
from ..states import AddFlow
from ..utils import (
    format_category_path,
    get_user_name,
    get_next_level,
    is_allowed,
    normalize_kind,
    parse_amount,
    render_amount,
)


async def on_add_income(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.update_data(kind="income")
    await state.set_state(AddFlow.waiting_amount)
    await edit_or_answer(
        callback,
        "💰 Введите сумму в формате 1000,00:",
        reply_markup=build_cancel_kb(),
    )
    await callback.answer()


async def on_add_expense(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.update_data(kind="expense")
    await state.set_state(AddFlow.waiting_amount)
    await edit_or_answer(
        callback,
        "💸 Введите сумму в формате 1000,00:",
        reply_markup=build_cancel_kb(),
    )
    await callback.answer()


async def on_amount(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    try:
        amount = parse_amount(message.text)
    except ValueError:
        await message.answer("⚠️ Не смог распознать сумму. Пример: 1000,00")
        await delete_user_message(message)
        return
    await state.update_data(amount=str(amount))
    data = await state.get_data()
    kind = data.get("kind", "")
    category_paths = await load_categories_from_sheet(kind)
    prefix = []
    options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_paths=category_paths,
        category_prefix=prefix,
        category_options=options,
    )
    text = "📂 Выберите категорию:" if options else "📂 Список категорий пуст. Добавьте новую."
    await state.set_state(AddFlow.waiting_category_select)
    await message.answer(
        text,
        reply_markup=build_category_kb(options, "➕ Добавить категорию", False),
    )
    await delete_user_message(message)


async def on_category_select(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    options = data.get("category_options", [])
    prefix = data.get("category_prefix", [])
    raw = callback.data or ""
    try:
        idx = int(raw.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Некорректная категория.", show_alert=True)
        return
    if idx < 0 or idx >= len(options):
        await callback.answer("⚠️ Категория не найдена.", show_alert=True)
        return
    prefix = prefix + [options[idx]]
    category_paths = data.get("category_paths", [])
    next_options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_prefix=prefix,
        category_options=next_options,
    )
    if next_options:
        text = "🧩 Выберите подкатегорию или нажмите Готово:"
    else:
        text = "🧩 Подкатегорий нет. Добавьте подкатегорию или нажмите Готово:"
    await edit_or_answer(
        callback,
        text,
        reply_markup=build_category_kb(next_options, "➕ Добавить подкатегорию", True),
    )
    await callback.answer()


async def on_category_done(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    if not prefix:
        await callback.answer("⚠️ Сначала выберите категорию.", show_alert=True)
        return
    await state.update_data(category=format_category_path(prefix))
    await state.set_state(AddFlow.waiting_comment)
    await edit_or_answer(
        callback,
        "💬 Комментарий:",
        reply_markup=build_comment_kb(),
    )
    await callback.answer()


async def on_category_add(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    if prefix:
        prompt = f"➕ Введите подкатегорию для '{format_category_path(prefix)}':"
    else:
        prompt = "➕ Введите новую категорию:"
    await state.set_state(AddFlow.waiting_category_add)
    await edit_or_answer(callback, prompt, reply_markup=build_cancel_kb())
    await callback.answer()


async def on_category_add_text(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    raw = message.text.strip()
    parts = [part.strip() for part in raw.split(">") if part.strip()]
    if not parts:
        await message.answer("⚠️ Категория не должна быть пустой.")
        await delete_user_message(message)
        return
    prefix = prefix + parts
    category_paths = data.get("category_paths", [])
    next_options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_prefix=prefix,
        category_options=next_options,
    )
    if next_options:
        text = "🧩 Выберите подкатегорию или нажмите Готово:"
    else:
        text = "🧩 Подкатегорий нет. Добавьте подкатегорию или нажмите Готово:"
    await state.set_state(AddFlow.waiting_category_select)
    await message.answer(
        text,
        reply_markup=build_category_kb(next_options, "➕ Добавить подкатегорию", True),
    )
    await delete_user_message(message)


async def save_entry(state: FSMContext, user_id: int, comment: str, send):
    data = await state.get_data()
    kind = normalize_kind(data.get("kind", "unknown"))
    amount = data.get("amount", "0")
    category = data.get("category", "")
    timestamp = datetime.now().strftime("%d.%m.%Y")
    row = [
        timestamp,
        kind,
        render_amount(Decimal(amount)),
        category,
        comment,
        get_user_name(user_id),
    ]
    try:
        await append_row(row)
    except Exception:
        logging.exception("Failed to append row")
        await send("❗ Ошибка записи в таблицу. Проверьте доступы.")
        return
    await state.clear()
    await send("✅ Записано.", reply_markup=build_main_kb())


async def on_comment(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    comment = message.text.strip()
    await save_entry(state, message.from_user.id, comment, message.answer)
    await delete_user_message(message)


async def on_comment_skip(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    async def send(text: str, reply_markup=None):
        await edit_or_answer(callback, text, reply_markup=reply_markup)

    await save_entry(state, callback.from_user.id, "", send)
    await callback.answer()


def register_finance(dp):
    dp.callback_query.register(on_add_income, F.data == "add_income")
    dp.callback_query.register(on_add_expense, F.data == "add_expense")
    dp.callback_query.register(on_category_select, F.data.startswith("cat_idx:"))
    dp.callback_query.register(on_category_add, F.data == "cat_add")
    dp.callback_query.register(on_category_done, F.data == "cat_done")
    dp.callback_query.register(on_comment_skip, F.data == "comment_skip")
    dp.message.register(on_amount, AddFlow.waiting_amount)
    dp.message.register(on_category_add_text, AddFlow.waiting_category_add)
    dp.message.register(on_comment, AddFlow.waiting_comment)
