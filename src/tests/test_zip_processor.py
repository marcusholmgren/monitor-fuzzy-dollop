import json
import logging
from unittest.mock import patch

import pytest

from src.zip_processor import ZipFileProcessor, main, parse_args, setup_logger


def test_parse_args_defaults():
    args = parse_args(["file1.zip", "file2.zip"])
    assert args.files == ["file1.zip", "file2.zip"]
    assert args.min_delay == 2.0
    assert args.max_delay == 5.0
    assert args.delay is None
    assert args.state_file is None
    assert args.log_level == "INFO"


def test_parse_args_custom():
    args = parse_args([
        "archive.zip",
        "--min-delay", "1.5",
        "--max-delay", "3.0",
        "--delay", "2.5",
        "--state-file", "/tmp/state.json",
        "--log-level", "DEBUG",
    ])
    assert args.files == ["archive.zip"]
    assert args.min_delay == 1.5
    assert args.max_delay == 3.0
    assert args.delay == 2.5
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


def test_main_cli_execution(tmp_path, capsys):
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
