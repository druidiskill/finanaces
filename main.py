import asyncio
import logging
import os
import time
from datetime import datetime
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
    kb.button(text="Добавить доход", callback_data="add_income")
    kb.button(text="Добавить расход", callback_data="add_expense")
    kb.button(text="Сводка", callback_data="summary")
    kb.adjust(1)
    return kb.as_markup()


def build_cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data="cancel")
    return kb.as_markup()


def build_comment_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Без комментариев", callback_data="comment_skip")
    kb.button(text="Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_category_kb(categories: list[str], add_label: str, show_done: bool):
    kb = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        kb.button(text=category, callback_data=f"cat_idx:{idx}")
    kb.button(text=add_label, callback_data="cat_add")
    if show_done:
        kb.button(text="Готово", callback_data="cat_done")
    kb.button(text="Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def normalize_kind(kind: str) -> str:
    if kind == "income":
        return "Доход"
    if kind == "expense":
        return "Расход"
    return kind


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


async def start(message: Message):
    if not is_allowed(message.from_user.id):
        print(message.chat.id)
        await message.answer("Доступ запрещен.")
        return
    await message.answer("Выберите действие:", reply_markup=build_main_kb())


async def on_start(message: Message):
    await start(message)


async def on_add_income(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await state.update_data(kind="income")
    await state.set_state(AddFlow.waiting_amount)
    await callback.message.answer(
        "Введите сумму в формате 1000,00:",
        reply_markup=build_cancel_kb(),
    )
    await callback.answer()


async def on_add_expense(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await state.update_data(kind="expense")
    await state.set_state(AddFlow.waiting_amount)
    await callback.message.answer(
        "Введите сумму в формате 1000,00:",
        reply_markup=build_cancel_kb(),
    )
    await callback.answer()


async def on_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=build_main_kb())
    await callback.answer()


async def on_amount(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("Доступ запрещен.")
        return
    try:
        amount = parse_amount(message.text)
    except ValueError:
        await message.answer("Не смог распознать сумму. Пример: 1000,00")
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
        text = "Выберите категорию:"
    else:
        text = "Список категорий пуст. Добавьте новую."
    await state.set_state(AddFlow.waiting_category_select)
    await message.answer(
        text,
        reply_markup=build_category_kb(options, "Добавить категорию", False),
    )


async def on_category_select(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    options = data.get("category_options", [])
    prefix = data.get("category_prefix", [])
    raw = callback.data or ""
    try:
        idx = int(raw.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректная категория.", show_alert=True)
        return
    if idx < 0 or idx >= len(options):
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    prefix = prefix + [options[idx]]
    category_paths = data.get("category_paths", [])
    next_options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_prefix=prefix,
        category_options=next_options,
    )
    if next_options:
        text = "Выберите подкатегорию или нажмите Готово:"
    else:
        text = "Подкатегорий нет. Добавьте подкатегорию или нажмите Готово:"
    await callback.message.answer(
        text,
        reply_markup=build_category_kb(next_options, "Добавить подкатегорию", True),
    )
    await callback.answer()


async def on_category_done(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    if not prefix:
        await callback.answer("Сначала выберите категорию.", show_alert=True)
        return
    await state.update_data(category=format_category_path(prefix))
    await state.set_state(AddFlow.waiting_comment)
    await callback.message.answer(
        "Комментарий:",
        reply_markup=build_comment_kb(),
    )
    await callback.answer()


async def on_category_add(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    if prefix:
        prompt = f"Введите подкатегорию для '{format_category_path(prefix)}':"
    else:
        prompt = "Введите новую категорию:"
    await state.set_state(AddFlow.waiting_category_add)
    await callback.message.answer(prompt, reply_markup=build_cancel_kb())
    await callback.answer()


async def on_category_add_text(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("Доступ запрещен.")
        return
    data = await state.get_data()
    prefix = data.get("category_prefix", [])
    raw = message.text.strip()
    parts = split_category_path(raw)
    if not parts:
        await message.answer("Категория не должна быть пустой.")
        return
    prefix = prefix + parts
    data = await state.get_data()
    category_paths = data.get("category_paths", [])
    next_options = get_next_level(category_paths, prefix)
    await state.update_data(
        category_prefix=prefix,
        category_options=next_options,
    )
    if next_options:
        text = "Выберите подкатегорию или нажмите Готово:"
    else:
        text = "Подкатегорий нет. Добавьте подкатегорию или нажмите Готово:"
    await state.set_state(AddFlow.waiting_category_select)
    await message.answer(
        text,
        reply_markup=build_category_kb(next_options, "Добавить подкатегорию", True),
    )


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
        await send("Ошибка записи в таблицу. Проверьте доступы.")
        return
    await state.clear()
    await send("Записано.", reply_markup=build_main_kb())


async def on_comment(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("Доступ запрещен.")
        return
    comment = message.text.strip()
    await save_entry(state, message.from_user.id, comment, message.answer)


async def on_comment_skip(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await save_entry(state, callback.from_user.id, "", callback.message.answer)
    await callback.answer()


async def on_summary(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Доступ запрещен.", show_alert=True)
        return
    await callback.message.answer("Сводка в разработке.")
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
    dp.callback_query.register(on_category_select, F.data.startswith("cat_idx:"))
    dp.callback_query.register(on_category_add, F.data == "cat_add")
    dp.callback_query.register(on_category_done, F.data == "cat_done")
    dp.callback_query.register(on_comment_skip, F.data == "comment_skip")
    dp.message.register(on_amount, AddFlow.waiting_amount)
    dp.message.register(on_category_add_text, AddFlow.waiting_category_add)
    dp.message.register(on_comment, AddFlow.waiting_comment)
    dp.message.register(start)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    time.sleep(30)
