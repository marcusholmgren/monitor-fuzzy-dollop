import json
import logging
import sqlite3
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.domain.commands import ProcessUnprocessedZipFilesCommand, UpdateFileIngestionStatusCommand
from src.domain.models import FileIngestionRecord
from src.handlers.process_zip_files import ProcessUnprocessedZipFilesHandler, UpdateFileIngestionStatusHandler
from src.zip_processor import ZipFileProcessor, get_db_connection, main, parse_args, setup_logger


def test_parse_args_defaults():
    args = parse_args(["file1.zip", "file2.zip"])
    assert args.files == ["file1.zip", "file2.zip"]
    assert args.min_delay == 2.0
    assert args.max_delay == 5.0
    assert args.delay is None
    assert args.limit is None
    assert args.state_file is None
    assert args.log_level == "INFO"


def test_parse_args_no_files_db_defaults():
    args = parse_args([])
    assert args.files == []
    assert args.db_url is None
    assert args.limit is None


def test_parse_args_custom():
    args = parse_args([
        "archive.zip",
        "--db-url", "postgresql://user:pass@localhost:5432/test",
        "--min-delay", "1.5",
        "--max-delay", "3.0",
        "--delay", "2.5",
        "--limit", "10",
        "--state-file", "/tmp/state.json",
        "--log-level", "DEBUG",
    ])
    assert args.files == ["archive.zip"]
    assert args.db_url == "postgresql://user:pass@localhost:5432/test"
    assert args.min_delay == 1.5
    assert args.max_delay == 3.0
    assert args.delay == 2.5
    assert args.limit == 10
    assert args.state_file == "/tmp/state.json"
    assert args.log_level == "DEBUG"


def test_processor_validation():
    with pytest.raises(ValueError, match="Delays must be non-negative"):
        ZipFileProcessor(min_delay=-1.0)

    with pytest.raises(ValueError, match="min_delay cannot be greater than max_delay"):
        ZipFileProcessor(min_delay=5.0, max_delay=2.0)


def test_setup_logger():
    logger = setup_logger("DEBUG")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1


def test_process_file_flow_with_sleep_mock(tmp_path):
    state_file = tmp_path / "state.json"
    logger = setup_logger("INFO")
    processor = ZipFileProcessor(
        min_delay=3.0,
        max_delay=3.0,
        state_file=state_file,
        logger=logger,
    )

    with patch("time.sleep") as mock_sleep:
        success = processor.process_file("uploads/sample.zip")
        assert success is True
        mock_sleep.assert_called_once_with(3.0)

    assert "uploads/sample.zip" in processor.state
    entry = processor.state["uploads/sample.zip"]
    assert entry["status"] == "COMPLETED"
    assert entry["simulated_duration_seconds"] == 3.0
    assert "processed_at" in entry

    # Verify state saved to disk
    assert state_file.exists()
    disk_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "uploads/sample.zip" in disk_data
    assert disk_data["uploads/sample.zip"]["status"] == "COMPLETED"


def test_process_all_sequential(tmp_path):
    state_file = tmp_path / "state.json"
    processor = ZipFileProcessor(
        min_delay=0.1,
        max_delay=0.1,
        state_file=state_file,
    )

    sleep_calls = []

    def mock_sleep(d):
        sleep_calls.append(d)

    with patch("time.sleep", side_effect=mock_sleep):
        count = processor.process_all(["f1.zip", "f2.zip", "f3.zip"])

    assert count == 3
    assert len(sleep_calls) == 3
    assert len(processor.state) == 3
    assert set(processor.state.keys()) == {"f1.zip", "f2.zip", "f3.zip"}


def test_process_all_empty():
    processor = ZipFileProcessor()
    count = processor.process_all([])
    assert count == 0


def test_load_existing_state(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"old.zip": {"status": "COMPLETED", "processed_at": "2025-01-01T00:00:00Z"}}),
        encoding="utf-8",
    )

    processor = ZipFileProcessor(min_delay=0.01, max_delay=0.01, state_file=state_file)
    assert "old.zip" in processor.state

    with patch("time.sleep"):
        processor.process_file("new.zip")

    assert "old.zip" in processor.state
    assert "new.zip" in processor.state

    disk_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "old.zip" in disk_data
    assert "new.zip" in disk_data


def test_main_cli_execution_files(tmp_path, capsys):
    state_file = tmp_path / "state.json"
    with patch("time.sleep"):
        exit_code = main([
            "first.zip",
            "second.zip",
            "--delay", "1.0",
            "--state-file", str(state_file),
        ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "STAGE: STARTING" in captured.out
    assert "STAGE: PROCESSING" in captured.out
    assert "STAGE: COMPLETED" in captured.out
    assert "STATE_UPDATE: Marked 'first.zip'" in captured.out
    assert "STATE_UPDATE: Marked 'second.zip'" in captured.out


def test_main_cli_invalid_delay_range():
    exit_code = main(["file.zip", "--min-delay", "5.0", "--max-delay", "2.0"])
    assert exit_code == 1


# --- Database-Driven Processor Unit & Integration Tests ---

@pytest.fixture
def sqlite_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE file_ingestions (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT '2026-11-01 00:00:00'
        );
    """)
    conn.commit()
    return conn


def test_database_driven_handlers_with_sqlite(sqlite_db, caplog):
    record_id = uuid4()
    device_id = uuid4()
    file_hash = "a" * 64

    sqlite_db.execute(
        """
        INSERT INTO file_ingestions (id, device_id, file_hash, file_path, original_filename, file_size_bytes, file_count, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending');
        """,
        (str(record_id), str(device_id), file_hash, "/storage/sample.zip", "sample.zip", 1024, 2),
    )
    sqlite_db.commit()

    logger = setup_logger("INFO")
    handler = ProcessUnprocessedZipFilesHandler(sqlite_db, logger=logger)

    with caplog.at_level(logging.INFO), patch("time.sleep") as mock_sleep:
        cmd = ProcessUnprocessedZipFilesCommand(min_delay=2.0, max_delay=2.0)
        summary = handler.execute(cmd)
        mock_sleep.assert_called_once_with(2.0)

    assert summary.total_found == 1
    assert summary.processed_count == 1
    assert len(summary.processed_records) == 1
    assert summary.processed_records[0].id == record_id
    assert summary.processed_records[0].device_id == device_id
    assert summary.processed_records[0].file_hash == file_hash

    # Verify status changed in database
    cur = sqlite_db.cursor()
    cur.execute("SELECT status FROM file_ingestions WHERE id = ?", (str(record_id),))
    row = cur.fetchone()
    assert row[0] == "processed"

    # Verify log messages
    logs = caplog.text
    assert f"Found 1 unprocessed pending file record(s)" in logs
    assert f"Processing file ID [{record_id}] for Device [{device_id}]" in logs
    assert f"Completed simulated processing for file ID [{record_id}]" in logs
    assert f"Successfully updated status to 'processed'" in logs


def test_database_driven_empty_queue(sqlite_db, caplog):
    logger = setup_logger("INFO")
    handler = ProcessUnprocessedZipFilesHandler(sqlite_db, logger=logger)
    with caplog.at_level(logging.INFO):
        summary = handler.execute(ProcessUnprocessedZipFilesCommand(min_delay=1.0, max_delay=1.0))

    assert summary.total_found == 0
    assert summary.processed_count == 0
    assert "No unprocessed zip files found in database" in caplog.text


def test_database_processor_via_mock_psycopg_connection(caplog):
    record_id = uuid4()
    device_id = uuid4()
    file_hash = "b" * 64

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate fetch_unprocessed_records returning one record
    mock_cursor.fetchall.return_value = [
        (
            record_id,
            device_id,
            file_hash,
            "/storage/file.zip",
            "file.zip",
            2048,
            3,
            "pending",
            {"test": "val"},
            "2026-11-01T12:00:00Z",
        )
    ]
    mock_cursor.rowcount = 1

    processor = ZipFileProcessor(min_delay=2.0, max_delay=2.0, db_conn=mock_conn)

    with caplog.at_level(logging.INFO), patch("time.sleep") as mock_sleep:
        count = processor.process_from_database(delay=2.5)
        mock_sleep.assert_called_once_with(2.5)

    assert count == 1
    # Check UPDATE query execution
    executed_queries = [call.args[0] for call in mock_cursor.execute.call_args_list]
    assert any("UPDATE file_ingestions" in q for q in executed_queries)
    assert any("status = %(status)s" in q for q in executed_queries)


def test_main_cli_database_driven(tmp_path, capsys):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE file_ingestions (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT '2026-11-01 00:00:00'
        );
    """)
    record_id = uuid4()
    device_id = uuid4()
    conn.execute(
        "INSERT INTO file_ingestions (id, device_id, file_hash, file_path, original_filename, file_size_bytes, file_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
        (str(record_id), str(device_id), "c" * 64, "/path.zip", "test.zip", 500, 1),
    )
    conn.commit()
    conn.close()

    with patch("time.sleep"):
        exit_code = main([
            "--db-url", f"sqlite:///{db_file}",
            "--delay", "1.0",
        ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Initializing database-driven zip file processor" in captured.out
    assert "DATABASE_QUERY: Found 1 unprocessed pending file record(s)" in captured.out
    assert "PROCESSING_START" in captured.out
    assert "PROCESSING_COMPLETE" in captured.out
    assert "TRANSACTION: Successfully updated status to 'processed'" in captured.out
    assert "SUMMARY: Successfully processed and updated 1/1 file(s)" in captured.out
