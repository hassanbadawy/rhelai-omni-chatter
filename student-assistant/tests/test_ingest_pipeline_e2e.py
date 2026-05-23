"""End-to-end ingest: upload a small fixture PDF, wait for ready, verify artifacts.

Requires Docker Compose stack (Llama Stack + Docling + Ollama) running.
Skip when STUDENT_ASSISTANT_E2E=1 is not set.
"""
import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("STUDENT_ASSISTANT_E2E") != "1",
    reason="set STUDENT_ASSISTANT_E2E=1 with Docker Compose stack running",
)


@pytest.mark.skip(reason="MVP1 implementation pending")
async def test_upload_to_ready() -> None:
    """submit_upload → poll status → assert ready within 5 min, wiki.md exists."""
    raise NotImplementedError


@pytest.mark.skip(reason="MVP1 implementation pending")
async def test_resume_after_crash() -> None:
    """Submit, kill the worker mid-parse, restart; pipeline resumes and reaches ready."""
    raise NotImplementedError
