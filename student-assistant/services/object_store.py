"""Local-filesystem object store with an S3-shaped interface for MVP4+.

Layout:
    {storage_root}/raw/{student_id}/{material_id}/{original_filename}
    {storage_root}/md/{student_id}/{material_id}/document.md
    {storage_root}/md/{student_id}/{material_id}/wiki.md
    {storage_root}/md/{student_id}/{material_id}/chapters/ch1.md
    {storage_root}/md/{student_id}/{material_id}/chapters/ch2.md
    {storage_root}/images/{student_id}/{material_id}/{img_hash}.{ext}
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Subdirectory names — keep as constants so a future grep finds them.
_RAW_SUBDIR = "raw"
_MD_SUBDIR = "md"
_CHAPTERS_SUBDIR = "chapters"
_IMAGES_SUBDIR = "images"


class ObjectStore:
    """Filesystem-backed object store. All async methods offload I/O via `asyncio.to_thread`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser()
        # Ensure root exists at construction time so first writes succeed.
        self.root.mkdir(parents=True, exist_ok=True)

    # ----- path helpers (sync; ensure parent dir on call) -----

    def raw_path(self, student_id: str, material_id: str, filename: str) -> Path:
        d = self.root / _RAW_SUBDIR / student_id / material_id
        d.mkdir(parents=True, exist_ok=True)
        return d / filename

    def md_dir(self, student_id: str, material_id: str) -> Path:
        d = self.root / _MD_SUBDIR / student_id / material_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def chapters_dir(self, student_id: str, material_id: str) -> Path:
        d = self.md_dir(student_id, material_id) / _CHAPTERS_SUBDIR
        d.mkdir(parents=True, exist_ok=True)
        return d

    def images_dir(self, student_id: str, material_id: str) -> Path:
        d = self.root / _IMAGES_SUBDIR / student_id / material_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ----- async I/O methods -----

    async def save_bytes(self, dest: Path, content: bytes) -> None:
        """Write bytes atomically (best-effort: write+rename) without blocking the loop."""
        await asyncio.to_thread(self._save_bytes_sync, dest, content)

    async def save_text(self, dest: Path, content: str) -> None:
        """Write text (UTF-8) atomically without blocking the loop."""
        await asyncio.to_thread(self._save_text_sync, dest, content)

    async def read_bytes(self, src: Path) -> bytes:
        return await asyncio.to_thread(self._read_bytes_sync, src)

    async def read_text(self, src: Path) -> str:
        return await asyncio.to_thread(self._read_text_sync, src)

    async def exists(self, p: Path) -> bool:
        return await asyncio.to_thread(p.exists)

    # ----- sync helpers (run inside `to_thread`) -----

    @staticmethod
    def _save_bytes_sync(dest: Path, content: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(dest)

    @staticmethod
    def _save_text_sync(dest: Path, content: str) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(dest)

    @staticmethod
    def _read_bytes_sync(src: Path) -> bytes:
        return src.read_bytes()

    @staticmethod
    def _read_text_sync(src: Path) -> str:
        return src.read_text(encoding="utf-8")
