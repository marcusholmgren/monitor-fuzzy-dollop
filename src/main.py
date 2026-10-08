import contextlib
from typing import AsyncGenerator
from fastapi import FastAPI

from src.db.pool import lifespan_pool
from src.core.exceptions import (
    UnregisteredEntityError,
    InvalidCursorError,
    unregistered_entity_exception_handler,
    invalid_cursor_exception_handler,
)
from src.api.v1.ingestion import router as ingestion_router
from src.api.v1.readings import router as readings_router


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with lifespan_pool():
        yield


app = FastAPI(
    title="monitor-fuzzy-dollop",
    description="Asynchronous API for collecting and querying IoT sensor readings",
    version="0.1.0",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(UnregisteredEntityError, unregistered_entity_exception_handler)
app.add_exception_handler(InvalidCursorError, invalid_cursor_exception_handler)

# Routers
app.include_router(ingestion_router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(readings_router, prefix="/api/v1", tags=["Readings"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
