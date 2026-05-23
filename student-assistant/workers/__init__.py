"""One module per job kind. Each exposes an async `handle(job, deps)` function.

`registry.py` maps `JobKind` → handler; `services/jobs.py` JobWorker uses the
registry to dispatch. Workers are thin: they unpack `payload_json`, call into
the right `services/` and `ingest/` modules, and write status updates.

Workers MUST be idempotent. The job system will retry on failure; a half-completed
job that gets retried must produce the same final state as a clean run.
"""
