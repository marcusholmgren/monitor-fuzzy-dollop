from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReadingItem:
    sensor_id: UUID
    house_id: UUID
    recorded_at: datetime
    metric_value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IngestReadingsBatchCommand:
    items: list[ReadingItem]


from pathlib import Path


@dataclass(frozen=True, slots=True)
class IngestZipFileCommand:
    device_id: UUID
    metadata: dict[str, Any]
    filename: str
    content_stream: Any  # SpooledTemporaryFile from UploadFile
    storage_root: Path
