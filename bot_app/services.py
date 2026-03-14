from __future__ import annotations

from bot_app.config import Settings, load_settings
from database import FinancesDatabase


settings: Settings = load_settings()
database = FinancesDatabase(settings.db_path)
