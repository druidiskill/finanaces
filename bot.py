from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot_app.handlers import setup_routers
from bot_app.services import database, settings


async def main() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(setup_routers())

    try:
        await dispatcher.start_polling(bot)
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main())
