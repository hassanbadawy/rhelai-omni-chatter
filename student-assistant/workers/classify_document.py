"""Classify a converted document as chapter_data or exercise_sheet.

Payload: {"file_id": str}
Reads document.md, calls LLM to classify, updates classified_type on the file.
- chapter_data  → mark READY (no further processing for now)
- exercise_sheet → chain to extract_questions
"""

from __future__ import annotations

import json
import logging

from domain.enums import ClassifiedType, FileStatus, JobKind
from domain.models import Job
from services.ai_client import AIClient
from workers._deps import WorkerDeps

logger = logging.getLogger(__name__)

_CLASSIFY_SYSTEM = """You are a document classifier for a school assistant system.
Given the markdown content of a school document, determine if it is:
1. "chapter_data" — textbook content with explanations, definitions, examples, or theory
2. "exercise_sheet" — a worksheet, exam, quiz, or test with questions for students to answer

Respond ONLY with valid JSON, no other text:
{"classified_type": "chapter_data" | "exercise_sheet", "reason": "one sentence"}"""


async def handle(job: Job, deps: WorkerDeps) -> dict | None:
    payload = json.loads(job.payload_json)
    file_id: str = payload["file_id"]

    mf = await deps.storage.get_file(file_id)
    if mf is None:
        raise RuntimeError(f"classify_document: file {file_id} not found")

    if mf.storage_md_path is None:
        raise RuntimeError(f"classify_document: no markdown for file {file_id}")

    md_text = mf.storage_md_path.read_text(encoding="utf-8")

    # Truncate to first 8000 chars — enough to classify document type.
    snippet = md_text[:8000]

    base_url, model, api_key = await deps.settings.get_llm_config()
    client = AIClient(base_url, model, api_key)

    raw = await client.chat(
        [
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": snippet},
        ],
        temperature=0.0,
        max_tokens=256,
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(raw)
        classified_type = ClassifiedType(data["classified_type"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise RuntimeError(
            f"classify_document: LLM returned unexpected JSON for file {file_id}: {raw!r}"
        ) from e

    logger.info(
        "classify_document: file=%s classified_type=%s reason=%s",
        file_id, classified_type.value, data.get("reason", ""),
    )

    await deps.storage.update_file_classified(file_id, classified_type)

    if classified_type == ClassifiedType.CHAPTER_DATA:
        await deps.storage.update_file_status(file_id, FileStatus.READY, "Chapter data indexed")
        return {"classified_type": classified_type.value, "chained": None}

    # Exercise sheet → extract questions.
    await deps.storage.update_file_status(file_id, FileStatus.EXTRACTING, "Extracting questions")
    await deps.jobs.enqueue(
        JobKind.EXTRACT_QUESTIONS,
        {"file_id": file_id},
        student_id=job.student_id,
        parent_job_id=job.parent_job_id,
        idempotency_key=f"extract_questions:{file_id}",
    )

    return {"classified_type": classified_type.value, "chained": "extract_questions"}
