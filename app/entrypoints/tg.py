from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher

from app.bootstrap.container import get_container
from app.bootstrap.logging import configure_logging
from app.interfaces.messenger.tg.handlers import setup_routers


async def run() -> None:
    container = get_container()
    configure_logging(container.settings.log_level)

    bot = Bot(token=container.settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(setup_routers())

    try:
        await dispatcher.start_polling(bot)
    finally:
        container.close()


def main() -> None:
    asyncio.run(run())
