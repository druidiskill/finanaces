import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread_asyncio

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_USER_IDS = {
    int(user_id.strip())
    for user_id in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if user_id.strip()
}
USER_NAME_MAP = {}
for pair in os.getenv("USER_NAME_MAP", "").split(","):
    if ":" not in pair:
        continue
    user_id, name = pair.split(":", 1)
    user_id = user_id.strip()
    name = name.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in {'"', "'"}:
        name = name[1:-1].strip()
    if not user_id or not name:
        continue
    try:
        USER_NAME_MAP[int(user_id)] = name
    except ValueError:
        continue
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Sheet1").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class AddFlow(StatesGroup):
    waiting_amount = State()
    waiting_category_select = State()
    waiting_category_add = State()
    waiting_comment = State()


class SummaryFlow(StatesGroup):
    waiting_kind = State()
    waiting_period = State()
    waiting_range = State()
    waiting_category = State()


def ensure_env():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not GOOGLE_SHEET_ID:
        missing.append("GOOGLE_SHEET_ID")
    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        missing.append("GOOGLE_SERVICE_ACCOUNT_FILE")
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")


def get_creds():
    return Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )


agcm = gspread_asyncio.AsyncioGspreadClientManager(get_creds)


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


def build_main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕💰 Добавить доход", callback_data="add_income")
    kb.button(text="➖💸 Добавить расход", callback_data="add_expense")
    kb.button(text="📊 Сводка", callback_data="summary")
    kb.adjust(1)
    return kb.as_markup()


def build_cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel")
    return kb.as_markup()


def build_comment_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Без комментариев", callback_data="comment_skip")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_category_kb(categories: list[str], add_label: str, show_done: bool):
    kb = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        kb.button(text=f"📁 {category}", callback_data=f"cat_idx:{idx}")
    kb.button(text=add_label, callback_data="cat_add")
    if show_done:
        kb.button(text="✅ Готово", callback_data="cat_done")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_kind_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Доходы", callback_data="sum_kind:income")
    kb.button(text="💸 Расходы", callback_data="sum_kind:expense")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_period_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сегодня", callback_data="sum_period:today")
    kb.button(text="🗓️ 7 дней", callback_data="sum_period:7d")
    kb.button(text="🗓️ 30 дней", callback_data="sum_period:30d")
    kb.button(text="🧭 Диапазон", callback_data="sum_period:range")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_category_kb(categories: list[str], show_done: bool, show_all: bool):
    kb = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        kb.button(text=f"📁 {category}", callback_data=f"sum_cat_idx:{idx}")
    if show_done:
        kb.button(text="✅ Готово", callback_data="sum_cat_done")
    if show_all:
        kb.button(text="📦 Все категории", callback_data="sum_cat_all")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


async def edit_or_answer(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


async def delete_user_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def load_categories_from_sheet(kind: str) -> list[str]:
    try:
        client = await agcm.authorize()
        sheet = await client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = await sheet.worksheet(GOOGLE_WORKSHEET_NAME)
        kind_values = await worksheet.col_values(2)
        category_values = await worksheet.col_values(4)
    except Exception:
        logging.exception("Failed to load categories from sheet")
        return []
    categories = []
    seen = set()
    target_kind = normalize_kind(kind)
    for row_kind, row_category in zip(kind_values, category_values):
        if row_category is None:
            continue
        item = str(row_category).strip()
        if not item:
            continue
        kind_item = str(row_kind).strip()
        if kind_item == "kind" or kind_item == "тип":
            continue
        if target_kind and kind_item != target_kind:
            continue
        lower = item.lower()
        if lower in {"category", "category_path", "категория", "категория_path"}:
            continue
        if item in seen:
            continue
        seen.add(item)
        categories.append(item)
    return categories


def split_category_path(path_value: str) -> list[str]:
    return [part.strip() for part in str(path_value).split(">") if part.strip()]


def format_category_path(parts: list[str]) -> str:
    return " > ".join(parts)


def get_next_level(categories: list[str], prefix: list[str]) -> list[str]:
    options = []
    seen = set()
    for path_value in categories:
        parts = split_category_path(path_value)
        if len(parts) <= len(prefix):
            continue
        if parts[: len(prefix)] != prefix:
            continue
        next_part = parts[len(prefix)]
        if next_part in seen:
            continue
        seen.add(next_part)
        options.append(next_part)
    return options


def normalize_kind(kind: str) -> str:
    if kind == "income":
        return "Доход"
    if kind == "expense":
        return "Расход"
    return kind


def parse_sheet_amount(value: str) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace("\u00A0", "")
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_sheet_date(value: str):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_date_range(text: str):
    raw = text.replace("—", "-").replace("–", "-")
    parts = [item.strip() for item in raw.split("-") if item.strip()]
    if len(parts) != 2:
        return None, None
    start = parse_sheet_date(parts[0])
    end = parse_sheet_date(parts[1])
    if not start or not end:
        return None, None
    if end < start:
        start, end = end, start
    return start, end


def parse_amount(text: str) -> Decimal:
    normalized = text.strip().replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    return amount.quantize(Decimal("0.01"))


async def append_row(row: list[str]):
    client = await agcm.authorize()
    sheet = await client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = await sheet.worksheet(GOOGLE_WORKSHEET_NAME)
    await worksheet.append_row(
        row,
        value_input_option="USER_ENTERED",
        table_range="A1",
    )


def render_amount(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", ",")


async def load_rows_from_sheet() -> list[list[str]]:
    try:
        client = await agcm.authorize()
        sheet = await client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = await sheet.worksheet(GOOGLE_WORKSHEET_NAME)
        return await worksheet.get_all_values()
    except Exception:
        logging.exception("Failed to load rows from sheet")
        return []


def summarize_rows(rows: list[list[str]], kind: str, start_date, end_date, prefix: list[str]):
    total = Decimal("0.00")
    buckets: dict[str, Decimal] = {}
    target_kind = normalize_kind(kind)

    for row in rows:
        if len(row) < 4:
            continue
        date_value = parse_sheet_date(row[0])
        if not date_value:
            header = str(row[0]).strip().lower()
            if header in {"date", "дата", "timestamp"}:
                continue
            continue
        row_kind = str(row[1]).strip()
        if target_kind and row_kind != target_kind:
            continue
        if date_value < start_date or date_value > end_date:
            continue
        amount = parse_sheet_amount(row[2])
        if amount is None:
            continue
        category = str(row[3]).strip()
        parts = split_category_path(category)
        if prefix:
            if parts[: len(prefix)] != prefix:
                continue
            group_key = parts[len(prefix)] if len(parts) > len(prefix) else ""
        else:
            group_key = parts[0] if parts else ""
        total += amount
        if group_key:
            buckets[group_key] = buckets.get(group_key, Decimal("0.00")) + amount

    return total, buckets


def compute_net_profit(rows: list[list[str]]):
    income = Decimal("0.00")
    expense = Decimal("0.00")
    for row in rows:
        if len(row) < 3:
            continue
        row_kind = str(row[1]).strip()
        if row_kind in {"kind", "тип"}:
            continue
        amount = parse_sheet_amount(row[2])
        if amount is None:
            continue
        if row_kind == "Доход":
            income += amount
        elif row_kind == "Расход":
            expense += amount
    return income, expense, income - expense



async def start(message: Message):
    if not is_allowed(message.from_user.id):
        print(message.chat.id)
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    await message.answer("🔘 Выберите действие:", reply_markup=build_main_kb())
    await delete_user_message(message)


async def on_start(message: Message):
    await start(message)


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


async def on_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_answer(callback, "❌ Отменено.", reply_markup=build_main_kb())
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
    if options:
        text = "📂 Выберите категорию:"
    else:
        text = "📂 Список категорий пуст. Добавьте новую."
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
    parts = split_category_path(raw)
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
    user_name = USER_NAME_MAP.get(user_id, "unknown")
    row = [
        timestamp,
        kind,
        render_amount(Decimal(amount)),
        category,
        comment,
        user_name,
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


async def on_summary(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.clear()
    rows = await load_rows_from_sheet()
    income, expense, net = compute_net_profit(rows)
    text = "\n".join(
        [
            "💹 Чистая прибыль за все время:",
            f"Доходы: {render_amount(income)}",
            f"Расходы: {render_amount(expense)}",
            f"Итого: {render_amount(net)}",
        ]
    )
    await edit_or_answer(callback, text, reply_markup=build_summary_kind_kb())
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
    title = "🧾 Сводка"
    lines = [
        f"{title}",
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
    await callback.answer()


async def main():
    ensure_env()
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(on_add_income, F.data == "add_income")
    dp.callback_query.register(on_add_expense, F.data == "add_expense")
    dp.callback_query.register(on_cancel, F.data == "cancel")
    dp.callback_query.register(on_summary, F.data == "summary")
    dp.callback_query.register(on_summary_kind, F.data.startswith("sum_kind:"))
    dp.callback_query.register(on_summary_period, F.data.startswith("sum_period:"))
    dp.callback_query.register(on_summary_category_select, F.data.startswith("sum_cat_idx:"))
    dp.callback_query.register(on_summary_category_done, F.data == "sum_cat_done")
    dp.callback_query.register(on_summary_category_all, F.data == "sum_cat_all")
    dp.callback_query.register(on_category_select, F.data.startswith("cat_idx:"))
    dp.callback_query.register(on_category_add, F.data == "cat_add")
    dp.callback_query.register(on_category_done, F.data == "cat_done")
    dp.callback_query.register(on_comment_skip, F.data == "comment_skip")
    dp.message.register(on_amount, AddFlow.waiting_amount)
    dp.message.register(on_category_add_text, AddFlow.waiting_category_add)
    dp.message.register(on_comment, AddFlow.waiting_comment)
    dp.message.register(on_summary_range, SummaryFlow.waiting_range)
    dp.message.register(start)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    time.sleep(30)
