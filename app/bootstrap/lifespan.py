from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.bootstrap.container import get_container


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    container = get_container()
    try:
        yield
    finally:
        container.close()
