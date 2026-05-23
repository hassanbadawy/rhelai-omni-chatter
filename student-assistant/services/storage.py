"""SQLite via aiosqlite. Wraps connection lifecycle, migrations, and CRUD."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from domain.enums import ClassifiedType, FileStatus, QuestionType, UploadType
from domain.models import Grade, Material, MaterialFile, Question, Student

logger = logging.getLogger(__name__)

_MIGRATION_FILE_RE = re.compile(r"^v(\d{3,})_.*\.sql$")

_SQL_PRAGMAS = (
    "PRAGMA foreign_keys = ON;",
    "PRAGMA journal_mode = WAL;",
)

_SQL_CREATE_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
"""

_SQL_LIST_APPLIED_MIGRATIONS = "SELECT version FROM schema_migrations ORDER BY version;"
_SQL_RECORD_MIGRATION = (
    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?);"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(s: str | None) -> datetime | None:
    if s is None:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        logger.warning("Failed to parse datetime from sqlite: %r", s)
        return None


def _require_dt(s: str | None) -> datetime:
    return _parse_dt(s) or datetime.now(timezone.utc)


# ── Row mappers ───────────────────────────────────────────────────────────────

def _row_to_student(row: aiosqlite.Row) -> Student:
    return Student(
        id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        created_at=_require_dt(row["created_at"]),
    )


def _row_to_grade(row: aiosqlite.Row) -> Grade:
    return Grade(
        id=row["id"],
        student_id=row["student_id"],
        name=row["name"],
        created_at=_require_dt(row["created_at"]),
    )


def _row_to_material(row: aiosqlite.Row) -> Material:
    return Material(
        id=row["id"],
        student_id=row["student_id"],
        grade_id=row["grade_id"],
        title=row["title"],
        created_at=_require_dt(row["created_at"]),
    )


def _row_to_file(row: aiosqlite.Row) -> MaterialFile:
    return MaterialFile(
        id=row["id"],
        material_id=row["material_id"],
        student_id=row["student_id"],
        upload_type=UploadType(row["upload_type"]),
        classified_type=ClassifiedType(row["classified_type"]) if row["classified_type"] else None,
        original_filename=row["original_filename"],
        mime_type=row["mime_type"],
        storage_raw_path=Path(row["storage_raw_path"]),
        storage_md_path=Path(row["storage_md_path"]) if row["storage_md_path"] else None,
        status=FileStatus(row["status"]),
        status_detail=row["status_detail"],
        created_at=_require_dt(row["created_at"]),
    )


def _row_to_question(row: aiosqlite.Row) -> Question:
    return Question(
        id=row["id"],
        file_id=row["file_id"],
        material_id=row["material_id"],
        grade_id=row["grade_id"],
        q_type=QuestionType(row["q_type"]),
        question_text=row["question_text"],
        options_json=row["options_json"],
        answer=row["answer"],
        image_path=row["image_path"],
        table_json=row["table_json"],
        order_index=row["order_index"],
        created_at=_require_dt(row["created_at"]),
    )


# ── Storage class ─────────────────────────────────────────────────────────────

class Storage:
    """Owns the single aiosqlite connection. One instance per app process."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path).expanduser()
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Storage.connect() must be called before use.")
        return self._conn

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        for pragma in _SQL_PRAGMAS:
            await conn.execute(pragma)
        await conn.commit()
        self._conn = conn
        logger.debug("Storage connected to %s", self.db_path)

    async def close(self) -> None:
        if self._conn is None:
            return
        await self._conn.close()
        self._conn = None

    # ── migrations ────────────────────────────────────────────────────────────

    async def migrate(self, migrations_dir: Path) -> None:
        if self._conn is None:
            await self.connect()
        conn = self.conn
        await conn.executescript(_SQL_CREATE_SCHEMA_MIGRATIONS)
        await conn.commit()

        async with conn.execute(_SQL_LIST_APPLIED_MIGRATIONS) as cur:
            rows = await cur.fetchall()
        applied: set[int] = {int(r["version"]) for r in rows}

        migrations: list[tuple[int, Path]] = []
        for path in sorted(Path(migrations_dir).glob("v*.sql")):
            m = _MIGRATION_FILE_RE.match(path.name)
            if not m:
                logger.warning("Skipping non-migration file: %s", path.name)
                continue
            migrations.append((int(m.group(1)), path))

        for version, path in migrations:
            if version in applied:
                logger.debug("Migration v%03d already applied — skipping", version)
                continue
            sql = path.read_text(encoding="utf-8")
            logger.info("Applying migration v%03d (%s)", version, path.name)
            try:
                # executescript() auto-commits any open transaction before running.
                # Run it first, then record completion in a separate commit so the
                # bookkeeping survives a crash-after-script.
                await conn.executescript(sql)
                await conn.execute(_SQL_RECORD_MIGRATION, (version, _now_iso()))
                await conn.commit()
            except Exception as e:
                raise RuntimeError(f"Migration {path.name} failed: {e}") from e

    # ── students ──────────────────────────────────────────────────────────────

    async def insert_student(self, s: Student) -> None:
        await self.conn.execute(
            "INSERT INTO students (id, display_name, email, created_at) VALUES (?, ?, ?, ?);",
            (s.id, s.display_name, s.email, s.created_at.isoformat()),
        )
        await self.conn.commit()

    async def list_students(self) -> list[Student]:
        async with self.conn.execute(
            "SELECT * FROM students ORDER BY created_at DESC;"
        ) as cur:
            return [_row_to_student(r) for r in await cur.fetchall()]

    async def get_student(self, student_id: str) -> Student | None:
        async with self.conn.execute(
            "SELECT * FROM students WHERE id = ?;", (student_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_student(row) if row else None

    # ── grades ────────────────────────────────────────────────────────────────

    async def insert_grade(self, g: Grade) -> None:
        await self.conn.execute(
            "INSERT INTO grades (id, student_id, name, created_at) VALUES (?, ?, ?, ?);",
            (g.id, g.student_id, g.name, g.created_at.isoformat()),
        )
        await self.conn.commit()

    async def list_grades(self, student_id: str) -> list[Grade]:
        async with self.conn.execute(
            "SELECT * FROM grades WHERE student_id = ? ORDER BY created_at ASC;",
            (student_id,),
        ) as cur:
            return [_row_to_grade(r) for r in await cur.fetchall()]

    async def get_grade(self, grade_id: str) -> Grade | None:
        async with self.conn.execute(
            "SELECT * FROM grades WHERE id = ?;", (grade_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_grade(row) if row else None

    # ── materials ─────────────────────────────────────────────────────────────

    async def insert_material(self, m: Material) -> None:
        await self.conn.execute(
            "INSERT INTO materials (id, student_id, grade_id, title, created_at)"
            " VALUES (?, ?, ?, ?, ?);",
            (m.id, m.student_id, m.grade_id, m.title, m.created_at.isoformat()),
        )
        await self.conn.commit()

    async def list_materials(self, grade_id: str) -> list[Material]:
        async with self.conn.execute(
            "SELECT * FROM materials WHERE grade_id = ? ORDER BY created_at ASC;",
            (grade_id,),
        ) as cur:
            return [_row_to_material(r) for r in await cur.fetchall()]

    async def get_material(self, material_id: str) -> Material | None:
        async with self.conn.execute(
            "SELECT * FROM materials WHERE id = ?;", (material_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_material(row) if row else None

    # ── material files ────────────────────────────────────────────────────────

    async def insert_file(self, f: MaterialFile) -> None:
        await self.conn.execute(
            """INSERT INTO material_files (
                id, material_id, student_id, upload_type, classified_type,
                original_filename, mime_type, storage_raw_path, storage_md_path,
                status, status_detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                f.id,
                f.material_id,
                f.student_id,
                f.upload_type.value,
                f.classified_type.value if f.classified_type else None,
                f.original_filename,
                f.mime_type,
                str(f.storage_raw_path),
                str(f.storage_md_path) if f.storage_md_path else None,
                f.status.value,
                f.status_detail,
                f.created_at.isoformat(),
            ),
        )
        await self.conn.commit()

    async def list_files(self, material_id: str) -> list[MaterialFile]:
        async with self.conn.execute(
            "SELECT * FROM material_files WHERE material_id = ? ORDER BY created_at DESC;",
            (material_id,),
        ) as cur:
            return [_row_to_file(r) for r in await cur.fetchall()]

    async def get_file(self, file_id: str) -> MaterialFile | None:
        async with self.conn.execute(
            "SELECT * FROM material_files WHERE id = ?;", (file_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_file(row) if row else None

    async def update_file_status(
        self, file_id: str, status: FileStatus, detail: str | None = None
    ) -> None:
        await self.conn.execute(
            "UPDATE material_files SET status = ?, status_detail = ? WHERE id = ?;",
            (status.value, detail, file_id),
        )
        await self.conn.commit()

    async def update_file_md_path(self, file_id: str, md_path: Path) -> None:
        await self.conn.execute(
            "UPDATE material_files SET storage_md_path = ? WHERE id = ?;",
            (str(md_path), file_id),
        )
        await self.conn.commit()

    async def update_file_classified(
        self, file_id: str, classified_type: ClassifiedType
    ) -> None:
        await self.conn.execute(
            "UPDATE material_files SET classified_type = ? WHERE id = ?;",
            (classified_type.value, file_id),
        )
        await self.conn.commit()

    # ── question bank ─────────────────────────────────────────────────────────

    async def insert_question(self, q: Question) -> None:
        await self.conn.execute(
            """INSERT INTO question_bank (
                id, file_id, material_id, grade_id, q_type, question_text,
                options_json, answer, image_path, table_json, order_index, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                q.id,
                q.file_id,
                q.material_id,
                q.grade_id,
                q.q_type.value,
                q.question_text,
                q.options_json,
                q.answer,
                q.image_path,
                q.table_json,
                q.order_index,
                q.created_at.isoformat(),
            ),
        )
        await self.conn.commit()

    async def insert_questions_bulk(self, questions: list[Question]) -> None:
        rows = [
            (
                q.id, q.file_id, q.material_id, q.grade_id, q.q_type.value,
                q.question_text, q.options_json, q.answer, q.image_path,
                q.table_json, q.order_index, q.created_at.isoformat(),
            )
            for q in questions
        ]
        await self.conn.executemany(
            """INSERT INTO question_bank (
                id, file_id, material_id, grade_id, q_type, question_text,
                options_json, answer, image_path, table_json, order_index, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            rows,
        )
        await self.conn.commit()

    async def list_questions_for_file(self, file_id: str) -> list[Question]:
        async with self.conn.execute(
            "SELECT * FROM question_bank WHERE file_id = ? ORDER BY order_index ASC;",
            (file_id,),
        ) as cur:
            return [_row_to_question(r) for r in await cur.fetchall()]

    async def list_questions_for_material(self, material_id: str) -> list[Question]:
        async with self.conn.execute(
            "SELECT * FROM question_bank WHERE material_id = ? ORDER BY order_index ASC;",
            (material_id,),
        ) as cur:
            return [_row_to_question(r) for r in await cur.fetchall()]

    # ── app settings ──────────────────────────────────────────────────────────

    async def get_setting(self, key: str) -> str | None:
        async with self.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?;", (key,)
        ) as cur:
            row = await cur.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
            (key, value),
        )
        await self.conn.commit()

    async def get_all_settings(self) -> dict[str, str]:
        async with self.conn.execute("SELECT key, value FROM app_settings;") as cur:
            rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    async def seed_settings_if_empty(self, defaults: dict[str, str]) -> None:
        """Write defaults only for keys that don't exist yet."""
        for key, value in defaults.items():
            existing = await self.get_setting(key)
            if existing is None:
                await self.set_setting(key, value)

