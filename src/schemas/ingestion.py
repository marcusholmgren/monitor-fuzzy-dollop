from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, RootModel
from src.domain.commands import IngestReadingsBatchCommand, ReadingItem


class ReadingItemSchema(BaseModel):
    sensor_id: UUID
    house_id: UUID
    recorded_at: datetime
    metric_value: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> ReadingItem:
        return ReadingItem(
            sensor_id=self.sensor_id,
            house_id=self.house_id,
            recorded_at=self.recorded_at,
            metric_value=self.metric_value,
            metadata=self.metadata,
        )


class IngestReadingsRequest(RootModel[list[ReadingItemSchema]]):
    def to_command(self) -> IngestReadingsBatchCommand:
        items = [item.to_domain() for item in self.root]
        return IngestReadingsBatchCommand(items=items)


class IngestReadingsResponse(BaseModel):
    inserted: int
