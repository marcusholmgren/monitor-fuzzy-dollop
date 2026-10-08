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
