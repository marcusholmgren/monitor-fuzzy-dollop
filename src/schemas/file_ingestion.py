from pydantic import BaseModel


class IngestZipFileResponse(BaseModel):
    file_hash: str
    status: str  # "accepted" or "already_processed"
