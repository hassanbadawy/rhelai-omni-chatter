"""Job queue API + JobWorker asyncio task.

See `~/.claude/plans/student-assistant-architecture.md` section 20 for the
full design. MVP1 uses 4 job kinds:

    ingest_material (parent)
      └─► parse_document → compile_wiki → split_chapters

The JobWorker runs as an asyncio task inside the Flet process. Single
concurrency in MVP1 (one job at a time). MVP2 raises per-kind concurrency
caps. MVP4 splits the worker out to a separate process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

from domain.enums import JobKind, JobState
from domain.models import Job

if TYPE_CHECKING:
    from services.storage import Storage
    from workers._deps import WorkerDeps

logger = logging.getLogger(__name__)


# Exponential backoff schedule (seconds) — attempt #1 waits 30s, etc.
_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (30, 5 * 60, 30 * 60, 2 * 60 * 60)

# How long to sleep when the queue is empty before polling again.
_IDLE_SLEEP_SECONDS = 1.0

# Treat any RUNNING job whose started_at is older than this as crashed and reset to pending.
_STUCK_JOB_THRESHOLD = timedelta(minutes=30)


# ---- SQL constants ----------------------------------------------------------

_SQL_INSERT_JOB = """
INSERT INTO job_queue (
  id, kind, payload_json, student_id, parent_job_id, idempotency_key,
  state, priority, attempts, max_attempts,
  scheduled_at, next_retry_at, started_at, finished_at,
  last_error, result_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_SQL_FIND_BY_IDEM = """
SELECT * FROM job_queue
WHERE idempotency_key = ?
ORDER BY created_at DESC
LIMIT 1;
"""

# Pick one runnable job: pending, due, ordered by priority then schedule time.
_SQL_SELECT_NEXT_RUNNABLE = """
SELECT * FROM job_queue
WHERE state = 'pending'
  AND scheduled_at <= ?
  AND (next_retry_at IS NULL OR next_retry_at <= ?)
ORDER BY priority ASC, scheduled_at ASC, created_at ASC
LIMIT 1;
"""

_SQL_CLAIM_JOB = """
UPDATE job_queue
SET state = 'running',
    started_at = ?,
    attempts = attempts + 1
WHERE id = ? AND state = 'pending';
"""

_SQL_RESET_STUCK_JOBS = """
UPDATE job_queue
SET state = 'pending', next_retry_at = NULL
WHERE state = 'running' AND started_at < ?;
"""

_SQL_COMPLETE_JOB = """
UPDATE job_queue
SET state = 'done',
    finished_at = ?,
    result_json = ?
WHERE id = ?;
"""

_SQL_FAIL_JOB_RETRY = """
UPDATE job_queue
SET state = 'pending',
    next_retry_at = ?,
    last_error = ?
WHERE id = ?;
"""

_SQL_FAIL_JOB_TERMINAL = """
UPDATE job_queue
SET state = 'failed',
    finished_at = ?,
    last_error = ?
WHERE id = ?;
"""

_SQL_LIST_JOBS_FOR_MATERIAL = """
SELECT * FROM job_queue
WHERE json_extract(payload_json, '$.material_id') = ?
ORDER BY created_at ASC;
"""


# ---- Helpers ----------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _row_to_job(row) -> Job:
    return Job(
        id=row["id"],
        kind=JobKind(row["kind"]),
        payload_json=row["payload_json"],
        student_id=row["student_id"],
        parent_job_id=row["parent_job_id"],
        idempotency_key=row["idempotency_key"],
        state=JobState(row["state"]),
        priority=row["priority"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        scheduled_at=_parse_iso(row["scheduled_at"]),
        next_retry_at=_parse_iso(row["next_retry_at"]) if row["next_retry_at"] else None,
        started_at=_parse_iso(row["started_at"]) if row["started_at"] else None,
        finished_at=_parse_iso(row["finished_at"]) if row["finished_at"] else None,
        last_error=row["last_error"],
        result_json=row["result_json"],
        created_at=_parse_iso(row["created_at"]) or _now_utc(),
    )


def _parse_iso(s: str | None) -> datetime | None:
    if s is None:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _retry_delay_seconds(attempts: int) -> int:
    """Attempt index → backoff in seconds. attempts==1 means first failure."""
    if attempts <= 0:
        return _RETRY_BACKOFF_SECONDS[0]
    idx = min(attempts - 1, len(_RETRY_BACKOFF_SECONDS) - 1)
    return _RETRY_BACKOFF_SECONDS[idx]


# ---- Public API -------------------------------------------------------------


class Jobs:
    """API surface for enqueue / claim / complete / fail."""

    def __init__(self, storage: "Storage") -> None:
        self.storage = storage

    async def enqueue(
        self,
        kind: JobKind,
        payload: dict,
        *,
        student_id: str | None = None,
        parent_job_id: str | None = None,
        idempotency_key: str | None = None,
        scheduled_at: datetime | None = None,
        priority: int = 5,
        max_attempts: int = 3,
    ) -> Job:
        """Insert a `pending` row. Dedupes by idempotency_key (returns existing job if found)."""
        # Idempotency: if a job with this key exists and is not in a terminal failure
        # state, return it untouched. Re-running a `done` job is a no-op for the caller;
        # re-running a `failed` job would require an explicit requeue.
        if idempotency_key is not None:
            existing = await self._find_by_idempotency_key(idempotency_key)
            if existing is not None and existing.state != JobState.FAILED:
                logger.debug(
                    "enqueue: dedup hit for %s (existing job %s, state=%s)",
                    idempotency_key,
                    existing.id,
                    existing.state,
                )
                return existing

        job_id = uuid.uuid4().hex
        now = _now_utc()
        sched_iso = (scheduled_at or now).isoformat()
        created_iso = now.isoformat()

        conn = self.storage.conn
        await conn.execute(
            _SQL_INSERT_JOB,
            (
                job_id,
                kind.value,
                json.dumps(payload),
                student_id,
                parent_job_id,
                idempotency_key,
                JobState.PENDING.value,
                priority,
                0,
                max_attempts,
                sched_iso,
                None,
                None,
                None,
                None,
                None,
                created_iso,
            ),
        )
        await conn.commit()

        logger.info(
            "enqueue %s job_id=%s payload=%s",
            kind.value,
            job_id,
            json.dumps(payload)[:200],
        )

        return Job(
            id=job_id,
            kind=kind,
            payload_json=json.dumps(payload),
            student_id=student_id,
            parent_job_id=parent_job_id,
            idempotency_key=idempotency_key,
            state=JobState.PENDING,
            priority=priority,
            attempts=0,
            max_attempts=max_attempts,
            scheduled_at=scheduled_at or now,
            created_at=now,
        )

    async def _find_by_idempotency_key(self, key: str) -> Job | None:
        async with self.storage.conn.execute(_SQL_FIND_BY_IDEM, (key,)) as cur:
            row = await cur.fetchone()
        return _row_to_job(row) if row else None

    async def reset_stuck_jobs(self) -> int:
        """Reset jobs stuck in `running` past the threshold. Call on JobWorker startup."""
        threshold_iso = (_now_utc() - _STUCK_JOB_THRESHOLD).isoformat()
        cur = await self.storage.conn.execute(_SQL_RESET_STUCK_JOBS, (threshold_iso,))
        await self.storage.conn.commit()
        count = cur.rowcount or 0
        if count:
            logger.warning("Reset %d stuck job(s) to pending on startup", count)
        return count

    async def claim_next(self) -> Job | None:
        """Atomically pick one due, pending job; transition to `running`. Returns None if queue empty.

        Uses `BEGIN IMMEDIATE` to serialize claim with other workers in the same process.
        For MVP1 there's only one JobWorker, but this keeps the contract honest for v1.5+.
        """
        conn = self.storage.conn
        now_iso = _now_iso()

        await conn.execute("BEGIN IMMEDIATE;")
        try:
            async with conn.execute(_SQL_SELECT_NEXT_RUNNABLE, (now_iso, now_iso)) as cur:
                row = await cur.fetchone()
            if row is None:
                await conn.commit()
                return None
            job_id = row["id"]
            await conn.execute(_SQL_CLAIM_JOB, (now_iso, job_id))
            await conn.commit()
        except Exception:
            await conn.execute("ROLLBACK;")
            raise

        # Re-read to get fresh state/attempts/started_at.
        async with conn.execute(
            "SELECT * FROM job_queue WHERE id = ?;", (job_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_job(row) if row else None

    async def complete(self, job_id: str, result: dict | None = None) -> None:
        result_json = json.dumps(result) if result is not None else None
        await self.storage.conn.execute(
            _SQL_COMPLETE_JOB, (_now_iso(), result_json, job_id)
        )
        await self.storage.conn.commit()
        logger.info("complete job_id=%s", job_id)

    async def fail(self, job_id: str, error: str) -> None:
        """Mark failed if attempts >= max_attempts; otherwise schedule retry with backoff."""
        async with self.storage.conn.execute(
            "SELECT attempts, max_attempts FROM job_queue WHERE id = ?;", (job_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            logger.warning("fail(): job %s not found", job_id)
            return

        attempts = int(row["attempts"])
        max_attempts = int(row["max_attempts"])
        truncated_error = error[:1000]

        if attempts >= max_attempts:
            await self.storage.conn.execute(
                _SQL_FAIL_JOB_TERMINAL, (_now_iso(), truncated_error, job_id)
            )
            logger.error(
                "fail (terminal) job_id=%s attempts=%d max=%d error=%s",
                job_id,
                attempts,
                max_attempts,
                truncated_error[:200],
            )
        else:
            delay = _retry_delay_seconds(attempts)
            next_retry = (_now_utc() + timedelta(seconds=delay)).isoformat()
            await self.storage.conn.execute(
                _SQL_FAIL_JOB_RETRY, (next_retry, truncated_error, job_id)
            )
            logger.warning(
                "fail (will retry) job_id=%s attempts=%d delay=%ds error=%s",
                job_id,
                attempts,
                delay,
                truncated_error[:200],
            )
        await self.storage.conn.commit()

    async def list_for_material(self, material_id: str) -> list[Job]:
        """For UI status display on /material/{id}."""
        async with self.storage.conn.execute(
            _SQL_LIST_JOBS_FOR_MATERIAL, (material_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_job(r) for r in rows]


# Handler signature: takes the job + injected services, returns optional result dict.
JobHandler = Callable[[Job, "WorkerDeps"], Awaitable[dict | None]]


class JobWorker:
    """asyncio task that loops claim → run → complete/fail."""

    def __init__(
        self,
        jobs: Jobs,
        registry: dict[JobKind, JobHandler],
        deps: "WorkerDeps",
    ) -> None:
        self.jobs = jobs
        self.registry = registry
        self.deps = deps
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> asyncio.Task:
        """Start the worker as an asyncio task. Returns the task handle."""
        if self._task is not None and not self._task.done():
            return self._task
        self._running = True
        self._task = asyncio.create_task(self.run(), name="job-worker")
        return self._task

    def stop(self) -> None:
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def run(self) -> None:
        """Loop until cancelled. Sleep ~1s when queue is empty."""
        try:
            await self.jobs.reset_stuck_jobs()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to reset stuck jobs at startup; continuing")

        self._running = True
        while self._running:
            try:
                job = await self.jobs.claim_next()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("claim_next failed; sleeping before retry")
                await asyncio.sleep(_IDLE_SLEEP_SECONDS)
                continue

            if job is None:
                try:
                    await asyncio.sleep(_IDLE_SLEEP_SECONDS)
                except asyncio.CancelledError:
                    raise
                continue

            await self._dispatch(job)

    async def _dispatch(self, job: Job) -> None:
        handler = self.registry.get(job.kind)
        if handler is None:
            await self.jobs.fail(
                job.id, f"No registered handler for job kind {job.kind.value}"
            )
            return

        logger.info(
            "dispatch job_id=%s kind=%s attempt=%d",
            job.id,
            job.kind.value,
            job.attempts,
        )
        try:
            result = await handler(job, self.deps)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("Handler raised for job %s (%s)", job.id, job.kind.value)
            try:
                await self.jobs.fail(job.id, f"{type(e).__name__}: {e}")
            except Exception:  # noqa: BLE001
                logger.exception("Also failed to record failure for job %s", job.id)
            return

        try:
            await self.jobs.complete(job.id, cast(dict | None, result))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to mark job %s done after handler success", job.id)
