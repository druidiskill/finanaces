from __future__ import annotations

from app.bootstrap.container import get_container
from app.bootstrap.settings import Settings


container = get_container()
settings: Settings = container.settings
database = container.database
