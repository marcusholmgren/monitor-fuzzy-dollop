import json
from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Response, status
import psycopg

from src.api.dependencies import get_db_connection
from src.core.config import settings
from src.domain.commands import IngestZipFileCommand
from src.handlers.ingest_zip_file import IngestZipFileHandler
from src.schemas.file_ingestion import IngestZipFileResponse

router = APIRouter()


@router.post("/ingest/files", response_model=IngestZipFileResponse)
async def ingest_files(
    device_id: Annotated[UUID, Form(...)],
    conn: Annotated[psycopg.AsyncConnection, Depends(get_db_connection)],
    response: Response,
    metadata: Annotated[str, Form()] = "{}",
    file: UploadFile = File(...),
) -> IngestZipFileResponse:
    # Validate filename / content type if needed
    filename = file.filename or "upload.zip"
    if not (filename.endswith(".zip") or file.content_type == "application/zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file must be a zip archive.",
        )

    try:
        parsed_metadata: dict[str, Any] = json.loads(metadata) if metadata else {}
        if not isinstance(parsed_metadata, dict):
            raise ValueError("Metadata must be a JSON object")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON string provided for metadata: {e}",
        ) from e

    command = IngestZipFileCommand(
        device_id=device_id,
        metadata=parsed_metadata,
        filename=filename,
        content_stream=file.file,
        storage_root=settings.storage_path,
    )

    handler = IngestZipFileHandler(conn)
    result = await handler.execute(command)

    if result.is_duplicate:
        response.status_code = status.HTTP_200_OK
        return IngestZipFileResponse(
            file_hash=result.file_hash,
            status="already_processed",
        )
    else:
        response.status_code = status.HTTP_202_ACCEPTED
        return IngestZipFileResponse(
            file_hash=result.file_hash,
            status="accepted",
        )
