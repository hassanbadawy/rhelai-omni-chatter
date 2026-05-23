"""Enumerations used across modules. Stringly-typed for SQLite friendliness."""

from __future__ import annotations

from enum import StrEnum


class UploadType(StrEnum):
    MATERIAL = "material"
    EXERCISE_SHEET = "exercise_sheet"
    ANSWER_SHEET = "answer_sheet"


class ClassifiedType(StrEnum):
    CHAPTER_DATA = "chapter_data"
    EXERCISE_SHEET = "exercise_sheet"


class FileStatus(StrEnum):
    UPLOADING = "uploading"
    CONVERTING = "converting"    # Docling running
    CLASSIFYING = "classifying"  # LLM classifying doc type
    EXTRACTING = "extracting"    # LLM extracting questions
    READY = "ready"
    FAILED = "failed"


class QuestionType(StrEnum):
    MCQ = "mcq"
    TEXT_QNA = "text_qna"
    IMAGE_QNA = "image_qna"
    TRUE_OR_FALSE = "true_or_false"
    TABLE_COMPARISON = "table_comparison"


class JobKind(StrEnum):
    INGEST_FILE = "ingest_file"
    PARSE_DOCUMENT = "parse_document"
    CLASSIFY_DOCUMENT = "classify_document"
    EXTRACT_QUESTIONS = "extract_questions"


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
