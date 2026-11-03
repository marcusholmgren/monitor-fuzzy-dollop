"""Command handlers for querying, simulating processing, and updating zip file ingestion records."""

from __future__ import annotations

import contextlib
import logging
import random
import time
from typing import Any, Iterator
from uuid import UUID

from src.domain.commands import ProcessUnprocessedZipFilesCommand, UpdateFileIngestionStatusCommand
from src.domain.models import FileIngestionRecord, ProcessFilesSummary


@contextlib.contextmanager
def get_cursor(conn: Any) -> Iterator[Any]:
    """Provides a compatible cursor context for both psycopg and sqlite3 connections."""
    cur = conn.cursor()
    try:
        if hasattr(cur, "__enter__") and hasattr(cur, "__exit__"):
            with cur as c:
                yield c
        else:
            yield cur
    finally:
        if hasattr(cur, "close"):
            try:
                cur.close()
            except Exception:
                pass


def format_sql(sql: str, conn: Any) -> str:
    """Adapts named %(param)s placeholder style to :param if using sqlite3."""
    is_sqlite = type(conn).__module__.startswith("sqlite3")
    if is_sqlite:
        import re
        return re.sub(r"%\((\w+)\)s", r":\1", sql)
    return sql


class UpdateFileIngestionStatusHandler:
    """Updates the status of a specific file ingestion record in PostgreSQL."""

    def __init__(self, conn: Any, logger: logging.Logger | None = None):
        self.conn = conn
        self.logger = logger or logging.getLogger("zip_processor")

    def execute(self, command: UpdateFileIngestionStatusCommand) -> bool:
        """Executes the status update query using unique identifiers."""
        update_query = format_sql("""
            UPDATE file_ingestions
            SET status = %(status)s
            WHERE id = %(id)s AND device_id = %(device_id)s AND file_hash = %(file_hash)s;
        """, self.conn)

        params = {
            "id": str(command.id),
            "device_id": str(command.device_id),
            "file_hash": command.file_hash,
            "status": command.status,
        }

        # If connection has transaction manager (psycopg 3 connection.transaction()), use it
        if hasattr(self.conn, "transaction"):
            with self.conn.transaction():
                with get_cursor(self.conn) as cur:
                    cur.execute(update_query, params)
                    updated = (cur.rowcount > 0) if cur.rowcount is not None else False
        else:
            with get_cursor(self.conn) as cur:
                cur.execute(update_query, params)
                updated = (cur.rowcount > 0) if cur.rowcount is not None else False
            if hasattr(self.conn, "commit"):
                self.conn.commit()

        if updated:
            self.logger.info(
                "TRANSACTION: Successfully updated status to '%s' for file ID [%s], Device [%s], Hash [%s].",
                command.status,
                command.id,
                command.device_id,
                command.file_hash,
            )
        else:
            self.logger.warning(
                "TRANSACTION: No rows updated for file ID [%s], Device [%s], Hash [%s].",
                command.id,
                command.device_id,
                command.file_hash,
            )

        return updated


class ProcessUnprocessedZipFilesHandler:
    """Retrieves unprocessed records from PostgreSQL, simulates processing, and updates status."""

    def __init__(self, conn: Any, logger: logging.Logger | None = None):
        self.conn = conn
        self.logger = logger or logging.getLogger("zip_processor")
        self.update_handler = UpdateFileIngestionStatusHandler(conn, logger=self.logger)

    def fetch_unprocessed_records(self, limit: int | None = None) -> list[FileIngestionRecord]:
        """Queries the file_ingestions table for records with status = 'pending'."""
        query = """
            SELECT id, device_id, file_hash, file_path, original_filename,
                   file_size_bytes, file_count, status, metadata, created_at
            FROM file_ingestions
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """
        params: dict[str, Any] = {}
        if limit is not None and limit > 0:
            query += " LIMIT %(limit)s"
            params["limit"] = limit

        query = format_sql(query, self.conn)

        with get_cursor(self.conn) as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            rows = cur.fetchall()

        records: list[FileIngestionRecord] = []
        for row in rows:
            if isinstance(row, dict):
                r_id = row["id"]
                device_id = row["device_id"]
                file_hash = row["file_hash"]
                file_path = row["file_path"]
                original_filename = row["original_filename"]
                file_size_bytes = row["file_size_bytes"]
                file_count = row["file_count"]
                status = row["status"]
                metadata = row["metadata"]
                created_at = row["created_at"]
            else:
                (
                    r_id,
                    device_id,
                    file_hash,
                    file_path,
                    original_filename,
                    file_size_bytes,
                    file_count,
                    status,
                    metadata,
                    created_at,
                ) = row[:10]

            records.append(
                FileIngestionRecord(
                    id=r_id if isinstance(r_id, UUID) else UUID(str(r_id)),
                    device_id=device_id if isinstance(device_id, UUID) else UUID(str(device_id)),
                    file_hash=str(file_hash),
                    file_path=str(file_path),
                    original_filename=str(original_filename),
                    file_size_bytes=int(file_size_bytes),
                    file_count=int(file_count),
                    status=str(status),
                    metadata=metadata if isinstance(metadata, dict) else {},
                    created_at=created_at,
                )
            )

        self.logger.info("DATABASE_QUERY: Found %d unprocessed pending file record(s).", len(records))
        return records

    def simulate_processing(self, record: FileIngestionRecord, duration: float) -> None:
        """Simulates processing work by logging record details and sleeping for duration."""
        self.logger.info(
            "PROCESSING_START: Processing file ID [%s] for Device [%s] (Filename: '%s', Hash: '%s', Size: %d bytes, Files: %d)",
            record.id,
            record.device_id,
            record.original_filename,
            record.file_hash,
            record.file_size_bytes,
            record.file_count,
        )
        self.logger.info(
            "PROCESSING_SIMULATION: Simulating workload for file ID [%s] (pausing for %.2f seconds)...",
            record.id,
            duration,
        )
        time.sleep(duration)
        self.logger.info(
            "PROCESSING_COMPLETE: Completed simulated processing for file ID [%s] for Device [%s].",
            record.id,
            record.device_id,
        )

    def execute(self, command: ProcessUnprocessedZipFilesCommand) -> ProcessFilesSummary:
        """Executes the full pipeline: query, iterate, simulate, update."""
        records = self.fetch_unprocessed_records(limit=command.limit)
        if not records:
            self.logger.info("No unprocessed zip files found in database.")
            return ProcessFilesSummary(total_found=0, processed_count=0, processed_records=[])

        min_delay = command.delay if command.delay is not None else command.min_delay
        max_delay = command.delay if command.delay is not None else command.max_delay

        if min_delay < 0 or max_delay < 0:
            raise ValueError("Delays must be non-negative.")
        if min_delay > max_delay:
            raise ValueError("min_delay cannot be greater than max_delay.")

        processed: list[FileIngestionRecord] = []
        for index, record in enumerate(records, start=1):
            self.logger.info("=== Processing Record %d/%d ===", index, len(records))
            duration = min_delay if min_delay == max_delay else random.uniform(min_delay, max_delay)
            self.simulate_processing(record, duration)

            update_cmd = UpdateFileIngestionStatusCommand(
                id=record.id,
                device_id=record.device_id,
                file_hash=record.file_hash,
                status="processed",
            )
            success = self.update_handler.execute(update_cmd)
            if success:
                processed.append(record)

        self.logger.info(
            "SUMMARY: Successfully processed and updated %d/%d file(s) from 'pending' to 'processed'.",
            len(processed),
            len(records),
        )
        return ProcessFilesSummary(
            total_found=len(records),
            processed_count=len(processed),
            processed_records=processed,
        )
