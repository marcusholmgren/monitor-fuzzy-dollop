import psycopg
from psycopg.types.json import Jsonb
from src.domain.commands import IngestReadingsBatchCommand
from src.core.exceptions import UnregisteredEntityError


class IngestReadingsHandler:
    def __init__(self, conn: psycopg.AsyncConnection):
        self.conn = conn

    async def execute(self, command: IngestReadingsBatchCommand) -> int:
        if not command.items:
            return 0

        # 1. Extract distinct (sensor_id, house_id) pairs
        distinct_pairs = list({(item.sensor_id, item.house_id) for item in command.items})
        sensor_ids = [p[0] for p in distinct_pairs]
        house_ids = [p[1] for p in distinct_pairs]

        async with self.conn.transaction():
            async with self.conn.cursor() as cur:
                # 2. Verify all pairs exist in the database
                check_query = """
                    SELECT u.s_id, u.h_id
                    FROM unnest(%s::uuid[], %s::uuid[]) AS u(s_id, h_id)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM sensors s
                        WHERE s.id = u.s_id AND s.house_id = u.h_id
                    )
                """
                await cur.execute(check_query, (sensor_ids, house_ids))
                missing_rows = await cur.fetchall()

                if missing_rows:
                    missing_list = [
                        {"sensor_id": str(row[0]), "house_id": str(row[1])}
                        for row in missing_rows
                    ]
                    raise UnregisteredEntityError(missing_pairs=missing_list)

                # 3. Perform batch insert
                insert_query = """
                    INSERT INTO readings (house_id, sensor_id, recorded_at, metric_value, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (sensor_id, recorded_at) DO NOTHING
                """
                records = [
                    (
                        item.house_id,
                        item.sensor_id,
                        item.recorded_at,
                        item.metric_value,
                        Jsonb(item.metadata),
                    )
                    for item in command.items
                ]

                await cur.executemany(insert_query, records)
                inserted_count = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
                return inserted_count
