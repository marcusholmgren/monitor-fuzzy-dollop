from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
import psycopg

from src.api.dependencies import get_db_connection
from src.domain.queries import GetReadingsKeysetQuery
from src.handlers.get_readings import GetReadingsHandler
from src.schemas.readings import PaginatedReadingsResponse, ReadingResponseSchema

router = APIRouter()


@router.get("/readings", status_code=status.HTTP_200_OK, response_model=PaginatedReadingsResponse)
async def get_readings(
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
    house_id: Optional[UUID] = Query(None),
    sensor_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
) -> PaginatedReadingsResponse:
    query = GetReadingsKeysetQuery(
        house_id=house_id,
        sensor_id=sensor_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        cursor=cursor,
    )
    handler = GetReadingsHandler(conn)
    result = await handler.execute(query)
    return PaginatedReadingsResponse(
        items=[ReadingResponseSchema.from_domain(item) for item in result.items],
        next_cursor=result.next_cursor,
    )
