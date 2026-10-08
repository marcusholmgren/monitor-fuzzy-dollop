from typing import Annotated
from fastapi import APIRouter, Depends, status
import psycopg

from src.api.dependencies import get_db_connection
from src.domain.commands import IngestReadingsBatchCommand
from src.handlers.ingest_readings import IngestReadingsHandler
from src.schemas.ingestion import ReadingItemSchema, IngestReadingsResponse

router = APIRouter()


@router.post("/readings", status_code=status.HTTP_201_CREATED, response_model=IngestReadingsResponse)
async def ingest_readings(
    payload: list[ReadingItemSchema],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
) -> IngestReadingsResponse:
    command = IngestReadingsBatchCommand(items=[item.to_domain() for item in payload])
    handler = IngestReadingsHandler(conn)
    inserted_count = await handler.execute(command)
    return IngestReadingsResponse(inserted=inserted_count)
