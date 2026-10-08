import base64
import json
from datetime import datetime
from uuid import UUID


def encode_cursor(recorded_at: datetime, reading_id: UUID) -> str:
    """Encodes recorded_at and reading_id into an opaque URL-safe Base64 token."""
    payload = {
        "recorded_at": recorded_at.isoformat(),
        "id": str(reading_id),
    }
    json_bytes = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decodes an opaque Base64 token back into (recorded_at, reading_id).

    Raises ValueError if invalid format.
    """
    try:
        json_bytes = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        payload = json.loads(json_bytes.decode("utf-8"))
        recorded_at = datetime.fromisoformat(payload["recorded_at"])
        reading_id = UUID(payload["id"])
        return recorded_at, reading_id
    except Exception as exc:
        raise ValueError(f"Invalid cursor format: {cursor}") from exc
