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
