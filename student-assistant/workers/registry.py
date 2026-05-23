"""Maps JobKind → handler function. Used by services.jobs.JobWorker."""

from __future__ import annotations

from domain.enums import JobKind
from services.jobs import JobHandler

from workers import classify_document, extract_questions, ingest_file, parse_document

REGISTRY: dict[JobKind, JobHandler] = {
    JobKind.INGEST_FILE: ingest_file.handle,
    JobKind.PARSE_DOCUMENT: parse_document.handle,
    JobKind.CLASSIFY_DOCUMENT: classify_document.handle,
    JobKind.EXTRACT_QUESTIONS: extract_questions.handle,
}
