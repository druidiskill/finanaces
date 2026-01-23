from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import caldav
import vobject

from .config import CALDAV_PASSWORD, CALDAV_URL, CALDAV_USERNAME


class CalDavConfigError(RuntimeError):
    pass


def get_client() -> caldav.DAVClient:
    if not CALDAV_URL or not CALDAV_USERNAME or not CALDAV_PASSWORD:
        raise CalDavConfigError("CalDav config is missing")
    return caldav.DAVClient(
        url=CALDAV_URL,
        username=CALDAV_USERNAME,
        password=CALDAV_PASSWORD,
    )


def list_calendars(client: caldav.DAVClient) -> list[caldav.Calendar]:
    principal = client.principal()
    return principal.calendars()


def resolve_calendar(client: caldav.DAVClient, calendar_id: str) -> caldav.Calendar:
    if calendar_id.startswith("http://") or calendar_id.startswith("https://"):
        return caldav.Calendar(client=client, url=calendar_id)

    calendars = list_calendars(client)
    for calendar in calendars:
        if calendar_id in str(calendar.url):
            return calendar
        name = getattr(calendar, "name", None)
        if name and name.strip() == calendar_id:
            return calendar
    raise CalDavConfigError(f"Calendar not found: {calendar_id}")


def get_display_name(calendar: caldav.Calendar) -> str:
    name = getattr(calendar, "name", None)
    if name:
        return name
    return str(calendar.url)


def _get_event_summary(vevent) -> str:
    summary = getattr(vevent, "summary", None)
    if summary and summary.value:
        return str(summary.value)
    return "Без названия"


def _get_event_description(vevent) -> str:
    description = getattr(vevent, "description", None)
    if description and description.value:
        return str(description.value)
    return ""


def _ensure_dtend(dtstart, dtend):
    if dtend:
        return dtend
    if isinstance(dtstart, datetime):
        return dtstart + timedelta(hours=1)
    if isinstance(dtstart, date):
        return dtstart + timedelta(days=1)
    return dtstart


def extract_event_info(event: caldav.Event) -> dict:
    vobj = event.vobject_instance
    vevent = vobj.vevent
    dtstart = vevent.dtstart.value
    dtend = getattr(vevent, "dtend", None)
    dtend_value = dtend.value if dtend else None
    description = _get_event_description(vevent)
    uid = getattr(vevent, "uid", None)
    uid_value = uid.value if uid else str(event.url)
    return {
        "uid": str(uid_value),
        "summary": _get_event_summary(vevent),
        "dtstart": dtstart,
        "dtend": _ensure_dtend(dtstart, dtend_value),
        "description": description,
        "url": str(event.url),
    }


def list_events(calendar: caldav.Calendar, start: datetime, end: datetime) -> list[dict]:
    events = calendar.date_search(start, end)
    return [extract_event_info(event) for event in events]


def parse_metadata(description: str) -> dict:
    data: dict[str, str] = {}
    for line in description.splitlines():
        if line.startswith("TM_") and "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def is_assigned(description: str) -> bool:
    return "TM_ASSIGNED_TO=" in description


def build_assigned_description(description: str, user_id: int, user_name: str) -> str:
    lines = []
    for line in description.splitlines():
        if line.startswith("TM_"):
            continue
        if line.startswith("Назначено:"):
            continue
        lines.append(line)
    meta = [
        f"TM_ASSIGNED_TO={user_id}",
        f"TM_ASSIGNED_NAME={user_name}",
    ]
    human = f"Назначено: {user_name}"
    merged = [human, *[line for line in lines if line.strip()], *meta]
    return "\n".join(merged).strip()


def build_personal_description(
    description: str,
    user_id: int,
    user_name: str,
    pool_uid: str,
    pool_url: str,
) -> str:
    base = description.strip()
    meta = [
        f"TM_ASSIGNED_TO={user_id}",
        f"TM_ASSIGNED_NAME={user_name}",
        f"TM_POOL_UID={pool_uid}",
        f"TM_POOL_URL={pool_url}",
    ]
    if base:
        return "\n".join([base, *meta])
    return "\n".join(meta)


def update_event_description(event: caldav.Event, description: str) -> None:
    vobj = event.vobject_instance
    vevent = vobj.vevent
    if hasattr(vevent, "description"):
        vevent.description.value = description
    else:
        vevent.add("description").value = description
    event.save()


def create_event(
    calendar: caldav.Calendar,
    summary: str,
    dtstart,
    dtend,
    description: str,
) -> None:
    cal = vobject.iCalendar()
    vevent = cal.add("vevent")
    vevent.add("uid").value = str(uuid4())
    vevent.add("summary").value = summary
    vevent.add("dtstart").value = dtstart
    vevent.add("dtend").value = dtend
    if description:
        vevent.add("description").value = description
    calendar.add_event(cal.serialize())


def load_event(client: caldav.DAVClient, event_url: str) -> caldav.Event:
    event = caldav.Event(client=client, url=event_url)
    event.load()
    return event
