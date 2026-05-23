"""Extract structured question bank from an exercise sheet markdown.

Payload: {"file_id": str}

Two-pass LLM approach:
  Pass 1 — Strip any existing answers (if student already solved it).
  Pass 2 — Convert to structured JSON question bank.

Each extracted image ref is saved to disk; image_path is stored in question_bank.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from domain.enums import FileStatus, QuestionType
from domain.models import Job, Question
from services.ai_client import AIClient
from workers._deps import WorkerDeps

logger = logging.getLogger(__name__)

_STRIP_ANSWERS_SYSTEM = """You are a teacher's assistant. You receive the markdown of an exercise sheet that a student may have already filled in.
Your job: remove ALL student-written answers while preserving every question intact.
- For MCQ: keep the choices, remove any selected/circled indication
- For text answers: remove any written text after "Answer:" lines
- For True/False: keep the question, remove any tick or circled choice
Return ONLY the cleaned markdown with questions intact but answers removed."""

_EXTRACT_SYSTEM = """You are a question bank builder for a school assistant system.
Extract ALL questions from this exercise sheet and return a JSON array.

For each question produce one object:
{
  "q_type": "mcq" | "text_qna" | "true_or_false" | "image_qna" | "table_comparison",
  "question_text": "the question stem (plain text, no answer)",
  "options": ["A. ...", "B. ...", ...] or null,
  "answer": "correct answer if an answer key is present, else null",
  "image_ref": "![...](data:image/...)" or null,
  "table": [["header1","header2"], ["row1col1","row1col2"]] or null,
  "order_index": 1
}

Rules:
- Set q_type="mcq" when there are lettered/numbered choices
- Set q_type="true_or_false" for T/F questions
- Set q_type="image_qna" when the question refers to a figure/image
- Set q_type="table_comparison" when a table is part of the question
- Set q_type="text_qna" for all other open-ended questions
- order_index starts at 1 and increments per question
- Return ONLY the JSON array, no other text"""


def _extract_image_base64(ref: str) -> bytes | None:
    """Extract base64 bytes from a markdown image data URI."""
    m = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", ref)
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1))
    except Exception:
        return None


async def handle(job: Job, deps: WorkerDeps) -> dict | None:
    payload = json.loads(job.payload_json)
    file_id: str = payload["file_id"]

    mf = await deps.storage.get_file(file_id)
    if mf is None:
        raise RuntimeError(f"extract_questions: file {file_id} not found")
    if mf.storage_md_path is None:
        raise RuntimeError(f"extract_questions: no markdown for file {file_id}")

    # Fetch parent entities for denormalised FK columns.
    material = await deps.storage.get_material(mf.material_id)
    if material is None:
        raise RuntimeError(f"extract_questions: material {mf.material_id} not found")

    base_url, model, api_key = await deps.settings.get_llm_config()
    client = AIClient(base_url, model, api_key)

    md_text = mf.storage_md_path.read_text(encoding="utf-8")

    # Pass 1: strip answers.
    cleaned_md = await client.chat(
        [
            {"role": "system", "content": _STRIP_ANSWERS_SYSTEM},
            {"role": "user", "content": md_text},
        ],
        temperature=0.0,
        max_tokens=8192,
    )
    logger.info("extract_questions: pass1 done for file=%s", file_id)

    # Pass 2: extract JSON.
    raw_json = await client.chat(
        [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {"role": "user", "content": cleaned_md},
        ],
        temperature=0.0,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    try:
        parsed = json.loads(raw_json)
        # LLM may wrap in {"questions": [...]} or return the array directly.
        if isinstance(parsed, dict):
            items = parsed.get("questions") or parsed.get("items") or list(parsed.values())[0]
        else:
            items = parsed
        if not isinstance(items, list):
            raise ValueError(f"Expected list, got {type(items)}")
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            f"extract_questions: LLM returned invalid JSON for file {file_id}: {e}\n{raw_json[:500]}"
        ) from e

    logger.info("extract_questions: pass2 extracted %d questions for file=%s", len(items), file_id)

    # Image directory for this file.
    img_dir = deps.object_store.storage_root / "images" / mf.student_id / mf.material_id / file_id
    img_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    questions: list[Question] = []

    for idx, item in enumerate(items):
        image_path: str | None = None
        image_ref = item.get("image_ref")
        if image_ref:
            img_bytes = _extract_image_base64(image_ref)
            if img_bytes:
                img_file = img_dir / f"q{idx + 1}.png"
                img_file.write_bytes(img_bytes)
                image_path = str(img_file)

        options = item.get("options")
        table = item.get("table")

        q = Question(
            id=uuid.uuid4().hex,
            file_id=file_id,
            material_id=mf.material_id,
            grade_id=material.grade_id,
            q_type=_parse_q_type(item.get("q_type", "text_qna")),
            question_text=str(item.get("question_text", "")).strip(),
            options_json=json.dumps(options) if options else None,
            answer=item.get("answer"),
            image_path=image_path,
            table_json=json.dumps(table) if table else None,
            order_index=int(item.get("order_index", idx + 1)),
            created_at=now,
        )
        questions.append(q)

    await deps.storage.insert_questions_bulk(questions)
    await deps.storage.update_file_status(
        file_id, FileStatus.READY,
        f"{len(questions)} questions extracted"
    )

    logger.info("extract_questions: done file=%s questions=%d", file_id, len(questions))
    return {"file_id": file_id, "question_count": len(questions)}


def _parse_q_type(raw: str) -> QuestionType:
    try:
        return QuestionType(raw.lower())
    except ValueError:
        return QuestionType.TEXT_QNA
