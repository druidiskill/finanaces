import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, ensure_env
from bot.handlers.common import register_common
from bot.handlers.finance import register_finance
from bot.handlers.goals import register_goals
from bot.handlers.summary import register_summary
from bot.handlers.time_management import register_time_management


async def main() -> None:
    ensure_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    register_common(dp)
    register_finance(dp)
    register_summary(dp)
    register_goals(dp)
    register_time_management(dp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
