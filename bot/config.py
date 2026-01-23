import os

from dotenv import load_dotenv

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
GOALS_WORKSHEET_NAME = os.getenv("GOALS_WORKSHEET_NAME", "Цели").strip()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CALDAV_URL = os.getenv("CALDAV_URL", "").strip()
CALDAV_USERNAME = os.getenv("CALDAV_USERNAME", "").strip()
CALDAV_PASSWORD = os.getenv("CALDAV_PASSWORD", "").strip()

CALDAV_POOL_CALENDARS = [
    value.strip()
    for value in os.getenv("CALDAV_POOL_CALENDARS", "").split(",")
    if value.strip()
]

CALDAV_USER_CALENDARS = {}
for pair in os.getenv("CALDAV_USER_CALENDARS", "").split(","):
    if ":" not in pair:
        continue
    user_id, calendar_id = pair.split(":", 1)
    user_id = user_id.strip()
    calendar_id = calendar_id.strip()
    if not user_id or not calendar_id:
        continue
    try:
        CALDAV_USER_CALENDARS[int(user_id)] = calendar_id
    except ValueError:
        continue


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
