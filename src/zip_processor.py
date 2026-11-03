"""Standalone Zip File Processor Service.

Queries PostgreSQL for unprocessed Zip file records in `file_ingestions`,
simulates the processing workflow (sleep/logging), and updates the status
to 'processed'. Adheres to the Command/Handler architectural pattern and
exclusively uses the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.domain.commands import ProcessUnprocessedZipFilesCommand
from src.handlers.process_zip_files import ProcessUnprocessedZipFilesHandler, UpdateFileIngestionStatusHandler


def setup_logger(level: str = "INFO") -> logging.Logger:
    """Configures and returns a timestamped logger."""
    logger = logging.getLogger("zip_processor")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_db_connection(database_url: str | None = None) -> Any:
    """Establishes and returns a database connection.

    Uses `psycopg` if available, or falls back to Python standard library
    database drivers (e.g. `sqlite3` for mock/test environments).
    """
    db_url = (
        database_url
        or os.environ.get("DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:5432/monitor_fuzzy_dollop"
    )

    if db_url.startswith("sqlite://"):
        import sqlite3

        db_path = db_url.removeprefix("sqlite://").removeprefix("/")
        if not db_path:
            db_path = ":memory:"
        conn = sqlite3.connect(db_path)
        return conn

    # Attempt psycopg (standard connection)
    try:
        import psycopg

        return psycopg.connect(db_url, autocommit=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to database at {db_url}: {exc}") from exc


class ZipFileProcessor:
    """Simulates processing and state management of Zip files.

    Can operate either directly against a PostgreSQL database via Command/Handler,
    or on explicit file paths/state file for standalone simulation.
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        state_file: str | Path | None = None,
        db_conn: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if min_delay < 0 or max_delay < 0:
            raise ValueError("Delays must be non-negative.")
        if min_delay > max_delay:
            raise ValueError("min_delay cannot be greater than max_delay.")

        self.min_delay = min_delay
        self.max_delay = max_delay
        self.state_file = Path(state_file) if state_file else None
        self.db_conn = db_conn
        self.logger = logger or setup_logger()
        self.state: dict[str, dict[str, str | float]] = {}
        if self.state_file and self.state_file.exists():
            self._load_state()

    def _load_state(self) -> None:
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except Exception as e:
            self.logger.warning("Could not load existing state from %s: %s", self.state_file, e)
            self.state = {}

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.logger.error("Failed to save state to %s: %s", self.state_file, e)

    def mark_as_processed(self, file_path_str: str, duration: float) -> None:
        """Simulates marking a file as processed in local state management."""
        record = {
            "status": "COMPLETED",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "simulated_duration_seconds": round(duration, 2),
        }
        self.state[file_path_str] = record
        self._save_state()
        self.logger.info("STATE_UPDATE: Marked '%s' as processed in tracking state.", file_path_str)

    def process_file(self, file_path_str: str) -> bool:
        """Executes the simulation loop for a single file path or identifier."""
        self.logger.info("STAGE: STARTING - Beginning processing for '%s'", file_path_str)

        duration = (
            self.min_delay
            if self.min_delay == self.max_delay
            else random.uniform(self.min_delay, self.max_delay)
        )

        self.logger.info(
            "STAGE: PROCESSING - Simulating work on '%s' (delay: %.2f seconds)",
            file_path_str,
            duration,
        )
        time.sleep(duration)

        self.logger.info(
            "STAGE: COMPLETED - Finished simulated work on '%s'",
            file_path_str,
        )
        self.mark_as_processed(file_path_str, duration)
        return True

    def process_all(self, files: Sequence[str]) -> int:
        """Processes a list of files sequentially."""
        if not files:
            self.logger.info("No files provided to process.")
            return 0

        self.logger.info("Beginning sequential processing of %d file(s).", len(files))
        processed_count = 0
        for index, file_path in enumerate(files, start=1):
            self.logger.info("--- File %d/%d ---", index, len(files))
            if self.process_file(file_path):
                processed_count += 1

        self.logger.info("All %d file(s) processed successfully.", processed_count)
        return processed_count

    def process_from_database(
        self,
        conn: Any | None = None,
        limit: int | None = None,
        delay: float | None = None,
    ) -> int:
        """Queries the database for unprocessed files and processes them via Command/Handler."""
        connection = conn or self.db_conn
        if connection is None:
            raise ValueError("No database connection available for database-driven processing.")

        handler = ProcessUnprocessedZipFilesHandler(connection, logger=self.logger)
        command = ProcessUnprocessedZipFilesCommand(
            min_delay=self.min_delay,
            max_delay=self.max_delay,
            delay=delay,
            limit=limit,
        )
        summary = handler.execute(command)
        return summary.processed_count


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Standalone Database-Driven Zip File Processor Service (Simulated Workflow).",
    )
    parser.add_argument(
        "files",
        nargs="*",
        default=[],
        help="Optional zip file paths or identifiers to process directly without DB.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL to connect to (e.g. postgresql://... or sqlite://...).",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
        help="Minimum simulated processing delay in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=5.0,
        help="Maximum simulated processing delay in seconds (default: 5.0).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Fixed simulated processing delay in seconds (overrides min/max delay if set).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unprocessed database records to process.",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default=None,
        help="Optional path to JSON state file to persist processed file tracking.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    return parser.parse_args(args)


def main(args: Sequence[str] | None = None) -> int:
    """Entrypoint for the console application."""
    parsed = parse_args(args)
    logger = setup_logger(parsed.log_level)

    min_delay = parsed.delay if parsed.delay is not None else parsed.min_delay
    max_delay = parsed.delay if parsed.delay is not None else parsed.max_delay

    if min_delay > max_delay:
        logger.error("Invalid arguments: min-delay (%.2f) cannot exceed max-delay (%.2f).", min_delay, max_delay)
        return 1

    # If explicit files are provided via CLI arguments, process them directly
    if parsed.files:
        processor = ZipFileProcessor(
            min_delay=min_delay,
            max_delay=max_delay,
            state_file=parsed.state_file,
            logger=logger,
        )
        processor.process_all(parsed.files)
        return 0

    # Otherwise, connect to PostgreSQL and process unprocessed records from file_ingestions
    logger.info("Initializing database-driven zip file processor...")
    conn = None
    try:
        conn = get_db_connection(parsed.db_url)
        processor = ZipFileProcessor(
            min_delay=min_delay,
            max_delay=max_delay,
            db_conn=conn,
            logger=logger,
        )
        processor.process_from_database(
            limit=parsed.limit,
            delay=parsed.delay,
        )
        return 0
    except Exception as e:
        logger.error("Database processing failed: %s", e)
        return 1
    finally:
        if conn is not None and hasattr(conn, "close"):
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
