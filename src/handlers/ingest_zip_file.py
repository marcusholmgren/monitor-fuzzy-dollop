import hashlib
import shutil
import zipfile
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb

from src.core.exceptions import InvalidZipFileError, FileCountExceededError
from src.domain.commands import IngestZipFileCommand
from src.domain.models import IngestionResult


class IngestZipFileHandler:
    def __init__(self, conn: psycopg.AsyncConnection):
        self.conn = conn

    async def execute(self, command: IngestZipFileCommand) -> IngestionResult:
        # 1. Hash calculation & stream sizing
        hasher = hashlib.sha256()
        file_size_bytes = 0

        command.content_stream.seek(0)
        while chunk := command.content_stream.read(8192):
            hasher.update(chunk)
            file_size_bytes += len(chunk)

        file_hash = hasher.hexdigest()

        # 2. Idempotency check in DB
        async with self.conn.transaction():
            async with self.conn.cursor() as cur:
                check_query = """
                    SELECT id, file_hash, file_path
                    FROM file_ingestions
                    WHERE device_id = %(device_id)s AND file_hash = %(file_hash)s;
                """
                await cur.execute(check_query, {"device_id": command.device_id, "file_hash": file_hash})
                existing = await cur.fetchone()

                if existing:
                    return IngestionResult(file_hash=file_hash, is_duplicate=True)

        # 3. Zip archive validation (if not duplicate)
        command.content_stream.seek(0)
        if not zipfile.is_zipfile(command.content_stream):
            raise InvalidZipFileError("Uploaded file is not a valid zip archive.")

        command.content_stream.seek(0)
        try:
            with zipfile.ZipFile(command.content_stream, "r") as zf:
                valid_files = [
                    info for info in zf.infolist()
                    if not info.is_dir()
                    and not info.filename.endswith("/")
                    and not info.filename.startswith("__MACOSX/")
                    and "/__MACOSX/" not in info.filename
                ]
        except zipfile.BadZipFile as e:
            raise InvalidZipFileError("Corrupted or invalid zip archive.") from e

        if not (1 <= len(valid_files) <= 4):
            raise FileCountExceededError(f"Zip archive contains {len(valid_files)} valid files, but must contain between 1 and 4 files.")

        # 4. Disk Storage
        dest_path = command.storage_root / str(command.device_id) / f"{file_hash}.zip"
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        command.content_stream.seek(0)
        with open(dest_path, "wb") as f_out:
            shutil.copyfileobj(command.content_stream, f_out)

        # 5. Database Persistence
        insert_query = """
            INSERT INTO file_ingestions (
                device_id, file_hash, file_path, metadata, original_filename, file_size_bytes, file_count
            ) VALUES (
                %(device_id)s, %(file_hash)s, %(file_path)s, %(metadata)s, %(original_filename)s, %(file_size_bytes)s, %(file_count)s
            )
            ON CONFLICT (device_id, file_hash) DO NOTHING
            RETURNING id;
        """
        params = {
            "device_id": command.device_id,
            "file_hash": file_hash,
            "file_path": str(dest_path),
            "metadata": Jsonb(command.metadata),
            "original_filename": command.filename,
            "file_size_bytes": file_size_bytes,
            "file_count": len(valid_files),
        }

        async with self.conn.transaction():
            async with self.conn.cursor() as cur:
                await cur.execute(insert_query, params)
                row = await cur.fetchone()

                # If race condition occurred and ON CONFLICT returned nothing
                if row is None:
                    return IngestionResult(file_hash=file_hash, is_duplicate=True)

        # 6. Return Result
        return IngestionResult(file_hash=file_hash, is_duplicate=False)
