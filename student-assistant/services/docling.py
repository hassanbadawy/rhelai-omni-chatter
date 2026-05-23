"""Docling client. Converts uploaded files into markdown.

Endpoint: POST {DOCLING_URL}/v1alpha/convert/source
Request shape includes the file (binary), `to_formats: ["md"]`, and
`image_export_mode: "embed"` so figures land inline as base64.

Latency budget: ~2 min for a 50-page PDF. The caller MUST be a background job
(see workers/parse_document.py); never call this from a UI handler.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Docling REST contract.
_CONVERT_PATH = "/v1alpha/convert/source"

# Default conversion parameters. The Docling server accepts these as a JSON blob
# alongside the multipart files field.
_DEFAULT_PARAMETERS: dict[str, Any] = {
    "to_formats": ["md"],
    "image_export_mode": "embed",
    "do_ocr": True,
    "do_table_structure": True,
}

# httpx timeout for a 50-page PDF: 5-min connect+read budget.
_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=300.0)


class DoclingError(RuntimeError):
    """Raised on any non-2xx response or invalid response shape from Docling."""


@dataclass(slots=True, frozen=True)
class DoclingResult:
    """Lightweight container for the docling response. Keep minimal."""

    markdown: str
    total_pages: int
    language: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class DoclingClient:
    """Async client for the Docling document conversion service."""

    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http

    async def convert_to_markdown(
        self, file_path: Path, mime_type: str
    ) -> DoclingResult:
        """POST /v1alpha/convert/source — returns parsed markdown + page count + figures."""
        url = f"{self.base_url}{_CONVERT_PATH}"
        file_path = Path(file_path)
        if not file_path.is_file():
            raise DoclingError(f"File not found: {file_path}")

        # Docling-serve accepts a multipart upload; the JSON parameters live in a
        # separate form field named `parameters`. The exact field names are
        # versioned — when in doubt, inspect {base_url}/docs.
        with file_path.open("rb") as fh:
            file_bytes = fh.read()

        files = {"files": (file_path.name, file_bytes, mime_type)}
        data = {"parameters": json.dumps(_DEFAULT_PARAMETERS)}

        logger.info(
            "Docling convert: file=%s size=%d bytes mime=%s",
            file_path.name,
            len(file_bytes),
            mime_type,
        )

        try:
            resp = await self.http.post(url, files=files, data=data, timeout=_TIMEOUT)
        except httpx.HTTPError as e:
            raise DoclingError(f"Docling request failed: {type(e).__name__}: {e}") from e

        if resp.status_code >= 400:
            body = resp.text[:500]
            raise DoclingError(
                f"Docling returned HTTP {resp.status_code}: {body}"
            )

        try:
            payload = resp.json()
        except json.JSONDecodeError as e:
            raise DoclingError(f"Docling response was not JSON: {e}") from e

        return _parse_response(payload)


def _parse_response(payload: dict[str, Any]) -> DoclingResult:
    """Extract markdown + page count from Docling's response payload.

    Docling responses have evolved across versions. Try multiple paths
    defensively:
      - `document.md_content` (current)
      - `document.markdown`
      - `result.md`
      - top-level `md_content`
    """
    document = payload.get("document") or {}
    markdown = (
        document.get("md_content")
        or document.get("markdown")
        or payload.get("md_content")
        or (payload.get("result") or {}).get("md")
    )
    if not isinstance(markdown, str) or not markdown.strip():
        raise DoclingError(
            "Docling response missing 'document.md_content' (or equivalent) — "
            "check Docling server version."
        )

    total_pages = (
        document.get("num_pages")
        or document.get("total_pages")
        or payload.get("num_pages")
        or _count_page_markers(markdown)
        or 1
    )

    language = (
        document.get("language")
        or payload.get("language")
    )

    return DoclingResult(
        markdown=markdown,
        total_pages=int(total_pages),
        language=language if isinstance(language, str) else None,
        raw_response=payload,
    )


def _count_page_markers(md: str) -> int:
    """Fallback page count from `<!-- page=N -->` markers."""
    import re

    matches = re.findall(r"<!--\s*page\s*[:=]?\s*(\d+)\s*-->", md, flags=re.IGNORECASE)
    return max((int(m) for m in matches), default=0)
