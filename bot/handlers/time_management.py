import asyncio
import logging
from datetime import date, datetime, timedelta

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..caldav_client import (
    CalDavConfigError,
    build_assigned_description,
    build_personal_description,
    extract_event_info,
    get_client,
    is_assigned,
    list_events,
    load_event,
    resolve_calendar,
)
from ..config import CALDAV_POOL_CALENDARS, CALDAV_USER_CALENDARS
from ..helpers import edit_or_answer
from ..keyboards import (
    build_time_assign_user_kb,
    build_time_my_kb,
    build_time_pool_events_kb,
    build_time_pools_kb,
    build_time_root_kb,
)
from ..states import TimeFlow
from ..utils import get_user_name, is_allowed

logger = logging.getLogger(__name__)


def _format_dt(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _format_event_range(dtstart, dtend) -> str:
    if isinstance(dtstart, datetime) and isinstance(dtend, datetime):
        if dtstart.date() == dtend.date():
            return f"{dtstart.strftime('%d.%m.%Y %H:%M')}-{dtend.strftime('%H:%M')}"
    return _format_dt(dtstart)


def _build_event_label(info: dict) -> str:
    time_part = _format_event_range(info["dtstart"], info["dtend"])
    return f"🗓 {time_part} • {info['summary']}"


def _sort_key(item: dict) -> datetime:
    dtstart = item.get("dtstart")
    if isinstance(dtstart, datetime):
        return dtstart
    if isinstance(dtstart, date):
        return datetime.combine(dtstart, datetime.min.time())
    return datetime.max


def _list_assign_users() -> list[dict]:
    users = []
    for user_id, calendar_id in CALDAV_USER_CALENDARS.items():
        users.append(
            {
                "id": user_id,
                "name": get_user_name(user_id),
                "calendar_id": calendar_id,
            }
        )
    users.sort(key=lambda item: item["name"])
    return users


def _fetch_calendar_events(calendar_id: str, days: int = 30) -> tuple[str, list[dict]]:
    client = get_client()
    calendar = resolve_calendar(client, calendar_id)
    now = datetime.now()
    events = list_events(calendar, now, now + timedelta(days=days))
    events.sort(key=_sort_key)
    return str(calendar.url), events


def _assign_event_to_user(
    pool_calendar_id: str,
    event_url: str,
    user_id: int,
    user_calendar_id: str,
) -> dict:
    client = get_client()
    pool_calendar = resolve_calendar(client, pool_calendar_id)
    user_calendar = resolve_calendar(client, user_calendar_id)

    pool_event = load_event(client, event_url)
    info = extract_event_info(pool_event)
    user_name = get_user_name(user_id)

    if is_assigned(info["description"]):
        raise CalDavConfigError("Задача уже назначена.")

    personal_description = build_personal_description(
        info["description"],
        user_id,
        user_name,
        info["uid"],
        info["url"],
    )

    from ..caldav_client import create_event, update_event_description

    create_event(
        user_calendar,
        info["summary"],
        info["dtstart"],
        info["dtend"],
        personal_description,
    )

    pool_description = build_assigned_description(info["description"], user_id, user_name)
    update_event_description(pool_event, pool_description)

    return info


async def on_section_time(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.clear()
    await edit_or_answer(
        callback,
        "⏱ Тайм-менеджмент — выберите действие:",
        reply_markup=build_time_root_kb(),
    )
    await callback.answer()


async def on_time_root(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_answer(
        callback,
        "⏱ Тайм-менеджмент — выберите действие:",
        reply_markup=build_time_root_kb(),
    )
    await callback.answer()


async def on_time_my(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    calendar_id = CALDAV_USER_CALENDARS.get(callback.from_user.id)
    if not calendar_id:
        await edit_or_answer(
            callback,
            "⚠️ Для вас не настроен личный календарь.",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    try:
        _, events = await asyncio.to_thread(_fetch_calendar_events, calendar_id, 7)
    except CalDavConfigError as exc:
        await edit_or_answer(
            callback,
            f"⚠️ Ошибка CalDav: {exc}",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    title = f"📅 Моё расписание на 7 дней ({get_user_name(callback.from_user.id)}):"
    if not events:
        text = f"{title}\n\nПока нет событий."
        await edit_or_answer(callback, text, reply_markup=build_time_my_kb())
        await callback.answer()
        return

    lines = [title, ""]
    for idx, item in enumerate(events[:20], start=1):
        lines.append(f"{idx}. {_build_event_label(item)}")
    if len(events) > 20:
        lines.append("…")
    await edit_or_answer(callback, "\n".join(lines), reply_markup=build_time_my_kb())
    await callback.answer()


async def on_time_pools(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.set_state(TimeFlow.choosing_pool)
    await state.update_data(time_mode="browse")

    if not CALDAV_POOL_CALENDARS:
        await edit_or_answer(
            callback,
            "⚠️ Список календарей-пулов пуст.",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    await edit_or_answer(
        callback,
        "📥 Выберите календарь-пул:",
        reply_markup=build_time_pools_kb(CALDAV_POOL_CALENDARS),
    )
    await callback.answer()


async def on_time_assign(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.set_state(TimeFlow.choosing_pool)
    await state.update_data(time_mode="assign")

    if not CALDAV_POOL_CALENDARS:
        await edit_or_answer(
            callback,
            "⚠️ Список календарей-пулов пуст.",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    await edit_or_answer(
        callback,
        "👤 Выберите календарь-пул для назначения:",
        reply_markup=build_time_pools_kb(CALDAV_POOL_CALENDARS),
    )
    await callback.answer()


async def on_time_pool_pick(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    if ":" not in callback.data:
        await callback.answer()
        return
    _, raw_idx = callback.data.split(":", 1)
    try:
        idx = int(raw_idx)
    except ValueError:
        await callback.answer()
        return
    if idx < 0 or idx >= len(CALDAV_POOL_CALENDARS):
        await callback.answer("⚠️ Некорректный выбор.", show_alert=True)
        return

    calendar_id = CALDAV_POOL_CALENDARS[idx]
    data = await state.get_data()
    mode = data.get("time_mode", "browse")
    await state.update_data(pool_calendar_id=calendar_id)

    try:
        _, events = await asyncio.to_thread(_fetch_calendar_events, calendar_id, 30)
    except CalDavConfigError as exc:
        await edit_or_answer(
            callback,
            f"⚠️ Ошибка CalDav: {exc}",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    if mode == "assign":
        events = [item for item in events if not is_assigned(item["description"])]

    if not events:
        await edit_or_answer(
            callback,
            "📭 В выбранном календаре пока нет доступных задач.",
            reply_markup=build_time_pools_kb(CALDAV_POOL_CALENDARS),
        )
        await callback.answer()
        return

    for item in events:
        item["label"] = _build_event_label(item)

    await state.set_state(TimeFlow.choosing_event)
    await state.update_data(pool_events=events)

    await edit_or_answer(
        callback,
        "📌 Выберите задачу:",
        reply_markup=build_time_pool_events_kb(events[:20]),
    )
    await callback.answer()


async def on_time_pool_event_pick(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    events = data.get("pool_events", [])
    mode = data.get("time_mode", "browse")
    if ":" not in callback.data:
        await callback.answer()
        return
    _, raw_idx = callback.data.split(":", 1)
    try:
        idx = int(raw_idx)
    except ValueError:
        await callback.answer()
        return
    if idx < 0 or idx >= len(events):
        await callback.answer("⚠️ Некорректный выбор.", show_alert=True)
        return

    selected = events[idx]
    await state.update_data(pool_event=selected)

    if mode != "assign":
        text = (
            f"📌 {selected['summary']}\n"
            f"🗓 { _format_event_range(selected['dtstart'], selected['dtend']) }\n"
        )
        if selected["description"]:
            text += f"\n📝 {selected['description']}"
        await edit_or_answer(
            callback,
            text,
            reply_markup=build_time_pool_events_kb(events[:20]),
        )
        await callback.answer()
        return

    users = _list_assign_users()
    if not users:
        await edit_or_answer(
            callback,
            "⚠️ Список исполнителей пуст.",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    await state.set_state(TimeFlow.choosing_assignee)
    await edit_or_answer(
        callback,
        "👤 Кому назначить задачу?",
        reply_markup=build_time_assign_user_kb(users),
    )
    await callback.answer()


async def on_time_assign_to(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    if ":" not in callback.data:
        await callback.answer()
        return
    _, raw_user_id = callback.data.split(":", 1)
    try:
        user_id = int(raw_user_id)
    except ValueError:
        await callback.answer()
        return

    data = await state.get_data()
    pool_event = data.get("pool_event")
    pool_calendar_id = data.get("pool_calendar_id")
    user_calendar_id = CALDAV_USER_CALENDARS.get(user_id)

    if not pool_event or not pool_calendar_id or not user_calendar_id:
        await edit_or_answer(
            callback,
            "⚠️ Не хватает данных для назначения.",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    try:
        info = await asyncio.to_thread(
            _assign_event_to_user,
            pool_calendar_id,
            pool_event["url"],
            user_id,
            user_calendar_id,
        )
    except CalDavConfigError as exc:
        await edit_or_answer(
            callback,
            f"⚠️ {exc}",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to assign event")
        await edit_or_answer(
            callback,
            f"⚠️ Ошибка назначения: {exc}",
            reply_markup=build_time_root_kb(),
        )
        await callback.answer()
        return

    await state.clear()
    await edit_or_answer(
        callback,
        f"✅ Назначено: {info['summary']} → {get_user_name(user_id)}",
        reply_markup=build_time_root_kb(),
    )
    await callback.answer()


def register_time_management(dp):
    dp.callback_query.register(on_section_time, lambda c: c.data == "section_time")
    dp.callback_query.register(on_time_root, lambda c: c.data == "time_root")
    dp.callback_query.register(on_time_my, lambda c: c.data == "time_my")
    dp.callback_query.register(on_time_pools, lambda c: c.data == "time_pools")
    dp.callback_query.register(on_time_assign, lambda c: c.data == "time_assign")
    dp.callback_query.register(on_time_pool_pick, lambda c: c.data.startswith("time_pool:"))
    dp.callback_query.register(
        on_time_pool_event_pick, lambda c: c.data.startswith("time_pool_event:")
    )
    dp.callback_query.register(on_time_assign_to, lambda c: c.data.startswith("time_assign_to:"))
