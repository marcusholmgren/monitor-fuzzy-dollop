from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
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


@dataclass(frozen=True, slots=True)
class IngestZipFileCommand:
    device_id: UUID
    metadata: dict[str, Any]
    filename: str
    content_stream: Any  # SpooledTemporaryFile from UploadFile
    storage_root: Path


@dataclass(frozen=True, slots=True)
class UpdateFileIngestionStatusCommand:
    id: UUID
    device_id: UUID
    file_hash: str
    status: str


@dataclass(frozen=True, slots=True)
class ProcessUnprocessedZipFilesCommand:
    min_delay: float = 2.0
    max_delay: float = 5.0
    delay: Optional[float] = None
    limit: Optional[int] = None
