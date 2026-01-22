from datetime import datetime, timedelta

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..helpers import delete_user_message, edit_or_answer
from ..keyboards import build_cancel_kb, build_main_kb, build_summary_category_kb, build_summary_kind_kb, build_summary_period_kb
from ..sheets import compute_net_profit, load_categories_from_sheet, load_rows_from_sheet, summarize_rows
from ..states import SummaryFlow
from ..utils import format_category_path, get_next_level, is_allowed, normalize_kind, parse_date_range, render_amount


async def on_summary(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.clear()
    rows = await load_rows_from_sheet()
    net = compute_net_profit(rows)
    await edit_or_answer(
        callback,
        f"💹 Чистая прибыль за все время: {render_amount(net)}",
        reply_markup=build_summary_kind_kb(),
    )
    await callback.answer()


async def on_summary_kind(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    raw = callback.data or ""
    kind = raw.split(":", 1)[1]
    await state.clear()
    await state.update_data(summary_kind=kind)
    await state.set_state(SummaryFlow.waiting_period)
    await edit_or_answer(
        callback,
        "🗓️ Выберите период:",
        reply_markup=build_summary_period_kb(),
    )
    await callback.answer()


async def on_summary_period(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    raw = callback.data or ""
    period = raw.split(":", 1)[1]
    today = datetime.now().date()
    if period == "today":
        start = end = today
    elif period == "7d":
        start, end = today - timedelta(days=6), today
    elif period == "30d":
        start, end = today - timedelta(days=29), today
    elif period == "range":
        await state.set_state(SummaryFlow.waiting_range)
        await edit_or_answer(
            callback,
            "🧭 Введите диапазон дат: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ",
            reply_markup=build_cancel_kb(),
        )
        await callback.answer()
        return
    else:
        await callback.answer("⚠️ Некорректный период.", show_alert=True)
        return

    await state.update_data(summary_start=start, summary_end=end)
    await state.set_state(SummaryFlow.waiting_category)
    data = await state.get_data()
    kind = data.get("summary_kind", "")
    category_paths = await load_categories_from_sheet(kind)
    prefix = []
    options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_paths=category_paths,
        category_prefix=prefix,
        category_options=options,
    )
    text = "📂 Выберите категорию или смотрите все:"
    await edit_or_answer(
        callback,
        text,
        reply_markup=build_summary_category_kb(options, show_done=False, show_all=True),
    )
    await callback.answer()


async def on_summary_range(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    start, end = parse_date_range(message.text)
    if not start or not end:
        await message.answer("⚠️ Неверный формат. Пример: 01.01.2026 - 31.01.2026")
        await delete_user_message(message)
        return
    await state.update_data(summary_start=start, summary_end=end)
    await state.set_state(SummaryFlow.waiting_category)
    data = await state.get_data()
    kind = data.get("summary_kind", "")
    category_paths = await load_categories_from_sheet(kind)
    prefix = []
    options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_paths=category_paths,
        category_prefix=prefix,
        category_options=options,
    )
    text = "📂 Выберите категорию или смотрите все:"
    await message.answer(
        text,
        reply_markup=build_summary_category_kb(options, show_done=False, show_all=True),
    )
    await delete_user_message(message)


async def on_summary_category_select(callback: CallbackQuery, state: FSMContext):
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
        text = "🧩 Подкатегорий нет. Нажмите Готово:"
    await edit_or_answer(
        callback,
        text,
        reply_markup=build_summary_category_kb(next_options, show_done=True, show_all=False),
    )
    await callback.answer()


async def on_summary_category_all(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.update_data(category_prefix=[])
    await show_summary(callback, state, show_all=True)
    await callback.answer()


async def on_summary_category_done(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await show_summary(callback, state, show_all=False)
    await callback.answer()


async def show_summary(callback: CallbackQuery, state: FSMContext, show_all: bool):
    data = await state.get_data()
    kind = data.get("summary_kind", "")
    start = data.get("summary_start")
    end = data.get("summary_end")
    prefix = data.get("category_prefix", [])
    if not start or not end:
        await edit_or_answer(callback, "⚠️ Период не задан.")
        return

    rows = await load_rows_from_sheet()
    total, buckets = summarize_rows(rows, kind, start, end, [] if show_all else prefix)
    prefix_label = "Все категории" if show_all or not prefix else format_category_path(prefix)
    lines = [
        "🧾 Сводка",
        f"Тип: {normalize_kind(kind)}",
        f"Период: {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}",
        f"Категория: {prefix_label}",
        f"Итого: {render_amount(total)}",
    ]
    if buckets:
        lines.append("Детализация:")
        items = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
        for name, amount in items[:15]:
            lines.append(f"• {name}: {render_amount(amount)}")
    await edit_or_answer(callback, "\n".join(lines), reply_markup=build_main_kb())
    await state.clear()


def register_summary(dp):
    dp.callback_query.register(on_summary, F.data == "summary")
    dp.callback_query.register(on_summary_kind, F.data.startswith("sum_kind:"))
    dp.callback_query.register(on_summary_period, F.data.startswith("sum_period:"))
    dp.callback_query.register(on_summary_category_select, F.data.startswith("sum_cat_idx:"))
    dp.callback_query.register(on_summary_category_done, F.data == "sum_cat_done")
    dp.callback_query.register(on_summary_category_all, F.data == "sum_cat_all")
    dp.message.register(on_summary_range, SummaryFlow.waiting_range)
