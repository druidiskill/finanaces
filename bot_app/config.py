from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ENV_PATH = Path(".env")


@dataclass(slots=True)
class Settings:
    bot_token: str
    allowed_user_ids: set[int]
    admin_user_ids: set[int]
    db_path: str
    log_level: str = "INFO"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_id_set(raw_value: str | None) -> set[int]:
    if not raw_value:
        return set()
    return {int(item.strip()) for item in raw_value.split(",") if item.strip()}


def load_settings() -> Settings:
    env = load_env()
    bot_token = env.get("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not configured in .env")

    allowed_user_ids = parse_id_set(env.get("ALLOWED_USER_IDS"))
    admin_user_ids = parse_id_set(env.get("ADMIN_USER_IDS")) or set(allowed_user_ids)

    return Settings(
        bot_token=bot_token,
        allowed_user_ids=allowed_user_ids,
        admin_user_ids=admin_user_ids,
        db_path=env.get("DB_PATH", "finances.db"),
        log_level=env.get("LOG_LEVEL", "INFO"),
    )
