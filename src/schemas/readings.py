from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel
from src.domain.models import ReadingReadModel


class ReadingResponseSchema(BaseModel):
    id: UUID
    house_id: UUID
    sensor_id: UUID
    recorded_at: datetime
    metric_value: float
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_domain(cls, model: ReadingReadModel) -> "ReadingResponseSchema":
        return cls(
            id=model.id,
            house_id=model.house_id,
            sensor_id=model.sensor_id,
            recorded_at=model.recorded_at,
            metric_value=model.metric_value,
            metadata=model.metadata,
            created_at=model.created_at,
        )


class PaginatedReadingsResponse(BaseModel):
    items: list[ReadingResponseSchema]
    next_cursor: Optional[str] = None
