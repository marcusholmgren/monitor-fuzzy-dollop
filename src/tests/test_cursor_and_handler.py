import pytest
from datetime import datetime, timezone
from uuid import uuid4
from src.core.cursor import encode_cursor, decode_cursor


def test_cursor_encoding_decoding():
    now = datetime.now(timezone.utc)
    reading_id = uuid4()

    cursor = encode_cursor(now, reading_id)
    assert isinstance(cursor, str)

    decoded_dt, decoded_id = decode_cursor(cursor)
    assert decoded_dt == now
    assert decoded_id == reading_id


def test_decode_invalid_cursor():
    with pytest.raises(ValueError, match="Invalid cursor format"):
        decode_cursor("invalid_base64_token_12345!")
