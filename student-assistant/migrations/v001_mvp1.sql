-- v001_mvp1 — MVP1 schema.
-- Scope: single hard-coded student, flat materials list, per-material chat,
-- background ingest pipeline (parse_document → compile_wiki → split_chapters).
-- No subjects, no embeddings, no quizzes, no flashcards, no auth tables.
-- MVP2+ adds these in subsequent v00N_*.sql migrations.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Identity (single hard-coded row in MVP1; full schema lands in MVP4).
CREATE TABLE IF NOT EXISTS students (
  id              TEXT PRIMARY KEY,
  email           TEXT,
  display_name    TEXT,
  created_at      TEXT NOT NULL
);

INSERT OR IGNORE INTO students (id, email, display_name, created_at)
VALUES ('student-mvp1', 'mvp1@local', 'MVP1 Student', strftime('%Y-%m-%dT%H:%M:%fZ','now'));

-- Materials.
CREATE TABLE IF NOT EXISTS materials (
  id                       TEXT PRIMARY KEY,
  student_id               TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  type                     TEXT NOT NULL DEFAULT 'material',  -- material only in MVP1; types 2/3/4 in MVP3
  title                    TEXT NOT NULL,
  original_filename        TEXT NOT NULL,
  mime_type                TEXT NOT NULL,
  storage_raw_path         TEXT NOT NULL,
  storage_md_path          TEXT,                              -- after parse_document
  wiki_summary_md          TEXT,                              -- after compile_wiki (cached)
  chapter_hierarchy_json   TEXT,                              -- parsed from wiki frontmatter
  total_pages              INTEGER,
  language                 TEXT,
  status                   TEXT NOT NULL DEFAULT 'uploading',
                                                              -- uploading | converting | indexing | ready | failed
  status_detail            TEXT,
  ingested_at              TEXT,
  created_at               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_student ON materials(student_id, created_at DESC);

-- Chat.
CREATE TABLE IF NOT EXISTS chat_sessions (
  id              TEXT PRIMARY KEY,
  student_id      TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  material_id     TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
  title           TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_material ON chat_sessions(material_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
  id              TEXT PRIMARY KEY,
  session_id      TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role            TEXT NOT NULL,                              -- user | assistant | system
  content         TEXT NOT NULL,
  citations_json  TEXT,                                       -- [{chapter_id, page_range}]
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);

-- Background jobs (see architecture spec section 20 for the full design).
-- MVP1 uses kinds: ingest_material | parse_document | compile_wiki | split_chapters
CREATE TABLE IF NOT EXISTS job_queue (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,
  payload_json    TEXT NOT NULL,
  student_id      TEXT REFERENCES students(id) ON DELETE CASCADE,
  parent_job_id   TEXT REFERENCES job_queue(id) ON DELETE CASCADE,
  idempotency_key TEXT,
  state           TEXT NOT NULL DEFAULT 'pending',            -- pending | running | done | failed | cancelled
  priority        INTEGER NOT NULL DEFAULT 5,
  attempts        INTEGER NOT NULL DEFAULT 0,
  max_attempts    INTEGER NOT NULL DEFAULT 3,
  scheduled_at    TEXT NOT NULL,
  next_retry_at   TEXT,
  started_at      TEXT,
  finished_at     TEXT,
  last_error      TEXT,
  result_json     TEXT,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_pending_scheduled ON job_queue(state, scheduled_at, priority);
CREATE INDEX IF NOT EXISTS idx_jobs_parent ON job_queue(parent_job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_idem ON job_queue(idempotency_key);

-- Schema version marker. Migration runner reads this and applies pending v00N_*.sql files.
CREATE TABLE IF NOT EXISTS schema_migrations (
  version  INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations (version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ','now'));
