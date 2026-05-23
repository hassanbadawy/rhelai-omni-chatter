"""Ingest orchestration. Called from upload_modal when a file is picked.

Persists a MaterialFile row, copies raw bytes to object store, then enqueues
the ingest_file job which fans out the conversion/classification pipeline.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from domain.enums import FileStatus, JobKind, UploadType
from domain.models import MaterialFile
from services.jobs import Jobs
from services.object_store import ObjectStore
from services.storage import Storage

logger = logging.getLogger(__name__)


class Ingest:
    def __init__(self, storage: Storage, object_store: ObjectStore, jobs: Jobs) -> None:
        self.storage = storage
        self.object_store = object_store
        self.jobs = jobs

    async def submit_upload(
        self,
        material_id: str,
        student_id: str,
        original_filename: str,
        mime_type: str,
        file_bytes: bytes,
        upload_type: UploadType = UploadType.EXERCISE_SHEET,
    ) -> MaterialFile:
        """Persist MaterialFile row + raw bytes; enqueue ingest_file job.

        1. INSERT material_file (status=uploading)
        2. Save bytes to object store
        3. UPDATE status=converting
        4. Enqueue ingest_file job
        5. Return fresh row
        """
        file_id = uuid.uuid4().hex
        raw_path = self.object_store.raw_path(student_id, material_id, original_filename)
        now = datetime.now(timezone.utc)

        mf = MaterialFile(
            id=file_id,
            material_id=material_id,
            student_id=student_id,
            upload_type=upload_type,
            original_filename=original_filename,
            mime_type=mime_type,
            storage_raw_path=raw_path,
            status=FileStatus.UPLOADING,
            status_detail="Saving file",
            created_at=now,
        )

        await self.storage.insert_file(mf)

        try:
            await self.object_store.save_bytes(raw_path, file_bytes)
        except Exception as e:
            await self.storage.update_file_status(
                file_id, FileStatus.FAILED, f"Save failed: {e}"
            )
            raise

        await self.storage.update_file_status(
            file_id, FileStatus.CONVERTING, "Queued for Docling"
        )

        await self.jobs.enqueue(
            JobKind.INGEST_FILE,
            {"file_id": file_id},
            student_id=student_id,
            idempotency_key=f"ingest:{file_id}",
        )

        logger.info(
            "submit_upload: file_id=%s material_id=%s upload_type=%s size=%d bytes",
            file_id, material_id, upload_type.value, len(file_bytes),
        )

        fresh = await self.storage.get_file(file_id)
        return fresh or mf
