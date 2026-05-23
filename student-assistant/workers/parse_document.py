"""Convert the raw uploaded file into Docling markdown.

Payload: {"file_id": str}
Reads storage_raw_path, calls DoclingClient (URL from SettingsService),
saves document.md, updates storage_md_path, then chains to classify_document.
"""

from __future__ import annotations

import json
import logging

import httpx

from domain.enums import FileStatus, JobKind
from domain.models import Job
from services.docling import DoclingClient
from workers._deps import WorkerDeps

logger = logging.getLogger(__name__)

_DOCUMENT_MD = "document.md"


async def handle(job: Job, deps: WorkerDeps) -> dict | None:
    payload = json.loads(job.payload_json)
    file_id: str = payload["file_id"]

    mf = await deps.storage.get_file(file_id)
    if mf is None:
        raise RuntimeError(f"parse_document: file {file_id} not found")

    md_dir = deps.object_store.md_dir(mf.student_id, mf.material_id)
    md_path = md_dir / _DOCUMENT_MD

    # Idempotency: if markdown already on disk and recorded, skip Docling.
    if mf.storage_md_path is not None and await deps.object_store.exists(md_path):
        logger.info("parse_document: cached markdown exists for file %s; skipping", file_id)
    else:
        # Build DoclingClient with URL from settings (runtime-editable without restart).
        docling_url = await deps.settings.get_docling_url()
        async with httpx.AsyncClient() as http:
            client = DoclingClient(docling_url, http)
            result = await client.convert_to_markdown(mf.storage_raw_path, mf.mime_type)

        await deps.object_store.save_text(md_path, result.markdown)
        await deps.storage.update_file_md_path(file_id, md_path)

        logger.info(
            "parse_document: file=%s pages=%d md=%d chars",
            file_id, result.total_pages, len(result.markdown),
        )

    await deps.storage.update_file_status(file_id, FileStatus.CLASSIFYING, "Classifying document")
    await deps.jobs.enqueue(
        JobKind.CLASSIFY_DOCUMENT,
        {"file_id": file_id},
        student_id=job.student_id,
        parent_job_id=job.parent_job_id,
        idempotency_key=f"classify_document:{file_id}",
    )

    return {"chained": "classify_document", "file_id": file_id}
