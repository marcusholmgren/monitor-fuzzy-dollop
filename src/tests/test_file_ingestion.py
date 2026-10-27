import io
import json
import zipfile
import hashlib
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
import pytest
from starlette.testclient import TestClient

from src.main import app
from src.api.dependencies import get_db_connection


def create_zip_bytes(files_dict: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for filename, content in files_dict.items():
            zf.writestr(filename, content)
    return buf.getvalue()


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

    cursor = MagicMock()
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=None)
    cursor.execute = AsyncMock(return_value=None)
    cursor.fetchone = AsyncMock(return_value=None)

    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def client(mock_conn):
    app.dependency_overrides[get_db_connection] = lambda: mock_conn
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_ingest_zip_file_success_first_time(client, mock_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.v1.file_ingestion.settings.storage_path", tmp_path)

    device_id = str(uuid4())
    zip_bytes = create_zip_bytes({"file1.txt": b"content1", "file2.txt": b"content2"})
    expected_hash = hashlib.sha256(zip_bytes).hexdigest()

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    # 1st fetchone for duplicate check -> None
    # 2nd fetchone for insert returning id -> ("some-uuid",)
    cursor.fetchone = AsyncMock(side_effect=[None, ("some-uuid",)])

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id, "metadata": json.dumps({"sensor": "A1"})},
        files={"file": ("data.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["file_hash"] == expected_hash
    assert data["status"] == "accepted"

    saved_file = tmp_path / device_id / f"{expected_hash}.zip"
    assert saved_file.exists()
    assert saved_file.read_bytes() == zip_bytes


def test_ingest_zip_file_duplicate(client, mock_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.v1.file_ingestion.settings.storage_path", tmp_path)

    device_id = str(uuid4())
    zip_bytes = create_zip_bytes({"file1.txt": b"content1"})
    expected_hash = hashlib.sha256(zip_bytes).hexdigest()

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    # fetchone returns existing record
    cursor.fetchone = AsyncMock(return_value=("existing-id", expected_hash, "path/to/file"))

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id},
        files={"file": ("data.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_hash"] == expected_hash
    assert data["status"] == "already_processed"

    saved_file = tmp_path / device_id / f"{expected_hash}.zip"
    assert not saved_file.exists()


def test_ingest_zip_file_corrupted(client, mock_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.v1.file_ingestion.settings.storage_path", tmp_path)

    device_id = str(uuid4())
    invalid_bytes = b"not a zip file content"

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchone = AsyncMock(return_value=None)

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id},
        files={"file": ("data.zip", invalid_bytes, "application/zip")},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "InvalidZipFileError"


def test_ingest_zip_file_zero_files(client, mock_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.v1.file_ingestion.settings.storage_path", tmp_path)

    device_id = str(uuid4())
    empty_zip_bytes = create_zip_bytes({})

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchone = AsyncMock(return_value=None)

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id},
        files={"file": ("data.zip", empty_zip_bytes, "application/zip")},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "FileCountExceededError"


def test_ingest_zip_file_exceed_max_files(client, mock_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.v1.file_ingestion.settings.storage_path", tmp_path)

    device_id = str(uuid4())
    five_files_zip = create_zip_bytes({
        "1.txt": b"1",
        "2.txt": b"2",
        "3.txt": b"3",
        "4.txt": b"4",
        "5.txt": b"5",
    })

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchone = AsyncMock(return_value=None)

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id},
        files={"file": ("data.zip", five_files_zip, "application/zip")},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "FileCountExceededError"


def test_ingest_zip_file_invalid_metadata_json(client, mock_conn):
    device_id = str(uuid4())
    zip_bytes = create_zip_bytes({"file1.txt": b"content1"})

    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id, "metadata": "invalid json {{"},
        files={"file": ("data.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 422


def test_ingest_zip_file_non_zip_extension(client, mock_conn):
    device_id = str(uuid4())
    response = client.post(
        "/api/v1/ingest/files",
        data={"device_id": device_id},
        files={"file": ("data.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 422
