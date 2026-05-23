"""Kick off the ingest pipeline for a newly-uploaded MaterialFile.

Payload: {"file_id": str}
Pipeline: ingest_file → parse_document → classify_document → (extract_questions?)
"""

from __future__ import annotations

import json
import logging

from domain.enums import FileStatus, JobKind
from domain.models import Job
from workers._deps import WorkerDeps

logger = logging.getLogger(__name__)


async def handle(job: Job, deps: WorkerDeps) -> dict | None:
    payload = json.loads(job.payload_json)
    file_id: str = payload["file_id"]

    mf = await deps.storage.get_file(file_id)
    if mf is None:
        raise RuntimeError(f"ingest_file: file {file_id} not found")

    await deps.storage.update_file_status(file_id, FileStatus.CONVERTING, "Running Docling")

    await deps.jobs.enqueue(
        JobKind.PARSE_DOCUMENT,
        {"file_id": file_id},
        student_id=job.student_id,
        parent_job_id=job.id,
        idempotency_key=f"parse_document:{file_id}",
    )

    return {"chained": "parse_document", "file_id": file_id}
