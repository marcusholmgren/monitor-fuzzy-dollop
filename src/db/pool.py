import contextlib
from typing import AsyncGenerator
from psycopg_pool import AsyncConnectionPool
from src.core.config import settings

pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.min_pool_size,
            max_size=settings.max_pool_size,
            open=False,
        )
        await pool.open()
    return pool


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    return pool


@contextlib.asynccontextmanager
async def lifespan_pool() -> AsyncGenerator[AsyncConnectionPool, None]:
    p = await init_pool()
    try:
        yield p
    finally:
        await close_pool()
