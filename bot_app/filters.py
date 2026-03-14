from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot_app.services import settings


class AllowedUserFilter(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user_id = _extract_user_id(event)
        return user_id in settings.allowed_user_ids


class AdminUserFilter(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user_id = _extract_user_id(event)
        return user_id in settings.admin_user_ids


def _extract_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message):
        return event.from_user.id if event.from_user else None
    if isinstance(event, CallbackQuery):
        return event.from_user.id if event.from_user else None
    return None
