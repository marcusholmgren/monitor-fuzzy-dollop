from typing import AsyncGenerator
import psycopg
from src.db.pool import get_pool


async def get_db_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    pool = get_pool()
    async with pool.connection() as conn:
        yield conn
