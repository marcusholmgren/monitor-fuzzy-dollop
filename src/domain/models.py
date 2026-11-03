from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReadingReadModel:
    id: UUID
    house_id: UUID
    sensor_id: UUID
    recorded_at: datetime
    metric_value: float
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PaginatedReadingsResult:
    items: list[ReadingReadModel]
    next_cursor: Optional[str]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    file_hash: str
    is_duplicate: bool


@dataclass(frozen=True, slots=True)
class FileIngestionRecord:
    id: UUID
    device_id: UUID
    file_hash: str
    file_path: str
    original_filename: str
    file_size_bytes: int
    file_count: int
    status: str
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProcessFilesSummary:
    total_found: int
    processed_count: int
    processed_records: list[FileIngestionRecord]
