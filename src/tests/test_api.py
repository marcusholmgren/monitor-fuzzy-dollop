import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from starlette.testclient import TestClient

from src.main import app
from src.api.dependencies import get_db_connection


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    # Mock transaction context manager
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)

    # Mock cursor context manager
    cursor = MagicMock()
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=None)
    cursor.execute = AsyncMock(return_value=None)
    cursor.executemany = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.rowcount = 1

    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def client(mock_conn):
    app.dependency_overrides[get_db_connection] = lambda: mock_conn
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_ingest_readings_success(client, mock_conn):
    sensor_id = str(uuid4())
    house_id = str(uuid4())
    payload = [
        {
            "sensor_id": sensor_id,
            "house_id": house_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metric_value": 22.5,
            "metadata": {"unit": "C"},
        }
    ]

    response = client.post("/api/v1/readings", json=payload)
    assert response.status_code == 201
    assert response.json() == {"inserted": 1}


def test_ingest_readings_unregistered_entity(client, mock_conn):
    sensor_id = str(uuid4())
    house_id = str(uuid4())
    payload = [
        {
            "sensor_id": sensor_id,
            "house_id": house_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metric_value": 22.5,
        }
    ]

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchall = AsyncMock(return_value=[(sensor_id, house_id)])

    response = client.post("/api/v1/readings", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "UnregisteredEntityError"
    assert len(data["missing"]) == 1


def test_ingest_readings_idempotency_zero_inserted(client, mock_conn):
    sensor_id = str(uuid4())
    house_id = str(uuid4())
    payload = [
        {
            "sensor_id": sensor_id,
            "house_id": house_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metric_value": 22.5,
        }
    ]

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchall = AsyncMock(return_value=[])  # All registered
    cursor.rowcount = 0  # Conflict resulted in 0 inserted

    response = client.post("/api/v1/readings", json=payload)
    assert response.status_code == 201
    assert response.json() == {"inserted": 0}


def test_get_readings_success(client, mock_conn):
    reading_id = uuid4()
    house_id = uuid4()
    sensor_id = uuid4()
    now = datetime.now(timezone.utc)

    cursor = mock_conn.cursor.return_value.__aenter__.return_value
    cursor.fetchall = AsyncMock(
        return_value=[
            {
                "id": reading_id,
                "house_id": house_id,
                "sensor_id": sensor_id,
                "recorded_at": now,
                "metric_value": 42.0,
                "metadata": {},
                "created_at": now,
            }
        ]
    )

    response = client.get("/api/v1/readings?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(reading_id)
    assert data["next_cursor"] is None
