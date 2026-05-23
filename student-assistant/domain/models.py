"""Pydantic models matching the SQLite schema.

These are the wire types between layers — services return these, views consume them.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .enums import ClassifiedType, FileStatus, JobKind, JobState, QuestionType, UploadType


class Student(BaseModel):
    id: str
    display_name: str
    email: str | None = None
    created_at: datetime


class Grade(BaseModel):
    id: str
    student_id: str
    name: str          # e.g. "Gr6", "Grade 7"
    created_at: datetime


class Material(BaseModel):
    id: str
    student_id: str
    grade_id: str
    title: str         # e.g. "Biology", "Math"
    created_at: datetime


class MaterialFile(BaseModel):
    id: str
    material_id: str
    student_id: str
    upload_type: UploadType = UploadType.EXERCISE_SHEET
    classified_type: ClassifiedType | None = None
    original_filename: str
    mime_type: str
    storage_raw_path: Path
    storage_md_path: Path | None = None
    status: FileStatus = FileStatus.UPLOADING
    status_detail: str | None = None
    created_at: datetime


class Question(BaseModel):
    id: str
    file_id: str
    material_id: str
    grade_id: str
    q_type: QuestionType
    question_text: str
    options_json: str | None = None    # JSON list for MCQ choices
    answer: str | None = None          # correct answer (stripped from sheet)
    image_path: str | None = None      # local disk path for IMAGE_QNA
    table_json: str | None = None      # 2D array JSON for TABLE_COMPARISON
    order_index: int = 0
    created_at: datetime


class AppSetting(BaseModel):
    key: str
    value: str


class Job(BaseModel):
    id: str
    kind: JobKind
    payload_json: str
    student_id: str | None = None
    parent_job_id: str | None = None
    idempotency_key: str | None = None
    state: JobState = JobState.PENDING
    priority: int = 5
    attempts: int = 0
    max_attempts: int = 3
    scheduled_at: datetime
    next_retry_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
    result_json: str | None = None
    created_at: datetime
