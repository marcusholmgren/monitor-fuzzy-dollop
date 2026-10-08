from fastapi import Request, status
from fastapi.responses import JSONResponse
from uuid import UUID


class DomainError(Exception):
    """Base domain exception."""
    pass


class UnregisteredEntityError(DomainError):
    """Raised when one or more (sensor_id, house_id) pairs do not exist in the database."""

    def __init__(self, missing_pairs: list[tuple[UUID, UUID]] | list[dict[str, str]]):
        self.missing_pairs = missing_pairs
        super().__init__(f"Unregistered entity pairs: {missing_pairs}")


class InvalidCursorError(DomainError):
    """Raised when an invalid cursor token is provided."""

    def __init__(self, cursor: str):
        self.cursor = cursor
        super().__init__(f"Invalid pagination cursor: {cursor}")


async def unregistered_entity_exception_handler(
    request: Request, exc: UnregisteredEntityError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "UnregisteredEntityError",
            "message": "One or more (sensor_id, house_id) pairs are not registered.",
            "missing": exc.missing_pairs,
        },
    )


async def invalid_cursor_exception_handler(
    request: Request, exc: InvalidCursorError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "InvalidCursorError",
            "message": str(exc),
        },
    )
