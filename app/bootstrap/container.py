from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap.settings import Settings, load_settings
from app.integrations.local.db.database import FinancesDatabase


@dataclass(slots=True)
class Container:
    settings: Settings
    database: FinancesDatabase

    @classmethod
    def build(cls) -> "Container":
        settings = load_settings()
        database = FinancesDatabase(settings.db_path)
        return cls(settings=settings, database=database)

    def close(self) -> None:
        self.database.close()


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container.build()
    return _container
