from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from src.domain.queries import GetReadingsKeysetQuery
from src.domain.models import ReadingReadModel, PaginatedReadingsResult
from src.core.cursor import decode_cursor, encode_cursor
from src.core.exceptions import InvalidCursorError


class GetReadingsHandler:
    def __init__(self, conn: psycopg.AsyncConnection):
        self.conn = conn

    async def execute(self, query: GetReadingsKeysetQuery) -> PaginatedReadingsResult:
        cursor_time: Optional[datetime] = None
        cursor_id: Optional[UUID] = None
        if query.cursor:
            try:
                cursor_time, cursor_id = decode_cursor(query.cursor)
            except ValueError as exc:
                raise InvalidCursorError(query.cursor) from exc

        where_clauses: list[str] = []
        params: dict[str, Any] = {}

        if cursor_time is not None and cursor_id is not None:
            where_clauses.append("(recorded_at, id) < (%(cursor_time)s, %(cursor_id)s)")
            params["cursor_time"] = cursor_time
            params["cursor_id"] = cursor_id

        if query.house_id is not None:
            where_clauses.append("house_id = %(house_id)s")
            params["house_id"] = query.house_id

        if query.sensor_id is not None:
            where_clauses.append("sensor_id = %(sensor_id)s")
            params["sensor_id"] = query.sensor_id

        if query.start_date is not None:
            where_clauses.append("recorded_at >= %(start_date)s")
            params["start_date"] = query.start_date

        if query.end_date is not None:
            where_clauses.append("recorded_at <= %(end_date)s")
            params["end_date"] = query.end_date

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        params["limit"] = query.limit

        sql = f"""
            SELECT id, house_id, sensor_id, recorded_at, metric_value, metadata, created_at
            FROM readings
            {where_sql}
            ORDER BY recorded_at DESC, id DESC
            LIMIT %(limit)s
        """

        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()

        items = [
            ReadingReadModel(
                id=row["id"],
                house_id=row["house_id"],
                sensor_id=row["sensor_id"],
                recorded_at=row["recorded_at"],
                metric_value=row["metric_value"],
                metadata=row["metadata"] if row["metadata"] is not None else {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

        next_cursor = None
        if len(items) == query.limit and items:
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.recorded_at, last_item.id)

        return PaginatedReadingsResult(items=items, next_cursor=next_cursor)
