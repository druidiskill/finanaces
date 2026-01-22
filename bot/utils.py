from datetime import datetime
from decimal import Decimal, InvalidOperation

from .config import ALLOWED_USER_IDS, USER_NAME_MAP


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


def normalize_kind(kind: str) -> str:
    if kind == "income":
        return "Доход"
    if kind == "expense":
        return "Расход"
    return kind


def format_status_ru(status: str) -> str:
    return {
        "todo": "В планах",
        "in_progress": "В процессе",
        "done": "Выполнено",
    }.get(status, status)


def status_emoji(status: str) -> str:
    return {
        "todo": "📝",
        "in_progress": "⚙️",
        "done": "✅",
    }.get(status, "📝")


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


def render_amount(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", ",")


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


def get_user_name(user_id: int) -> str:
    return USER_NAME_MAP.get(user_id, "unknown")
