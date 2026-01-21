import asyncio
import logging
import os
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
    waiting_category = State()
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
    await worksheet.append_row(row, value_input_option="USER_ENTERED")


def render_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


async def start(message: Message):
    if not is_allowed(message.from_user.id):
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
    await state.set_state(AddFlow.waiting_category)
    await message.answer(
        "Категория. Можно указать уровень через '>' (например: Дом > Коммунальные):",
        reply_markup=build_cancel_kb(),
    )

async def on_category(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("Доступ запрещен.")
        return
    category = message.text.strip()
    if not category:
        await message.answer("Категория не должна быть пустой.")
        return
    await state.update_data(category=category)
    await state.set_state(AddFlow.waiting_comment)
    await message.answer(
        "Комментарий (или '-' чтобы пропустить):",
        reply_markup=build_cancel_kb(),
    )


async def on_comment(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("Доступ запрещен.")
        return
    data = await state.get_data()
    kind = data.get("kind", "unknown")
    amount = data.get("amount", "0")
    category = data.get("category", "")
    comment = message.text.strip()
    if comment == "-":
        comment = ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_name = USER_NAME_MAP.get(message.from_user.id, "unknown")
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
        await message.answer("Ошибка записи в таблицу. Проверьте доступы.")
        return
    await state.clear()
    await message.answer("Записано.", reply_markup=build_main_kb())


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
    dp.message.register(on_amount, AddFlow.waiting_amount)
    dp.message.register(on_category, AddFlow.waiting_category)
    dp.message.register(on_comment, AddFlow.waiting_comment)
    dp.message.register(start)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
