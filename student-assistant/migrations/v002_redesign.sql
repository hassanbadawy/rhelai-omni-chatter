-- v002: Redesign — Student > Grade > Material > File hierarchy, question bank, test sessions
-- Removes: chat_messages, chat_sessions
-- Adds: grades, material_files, question_bank, test_sessions, test_answers, app_settings
-- Modifies: materials (add grade_id, drop wiki/chapter/status fields)

-- ─── Remove old chat tables ────────────────────────────────────────────────────
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS chat_sessions;

-- ─── Grades ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grades (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id, created_at);

-- ─── Rebuild materials with grade_id (SQLite can't ADD NOT NULL column with FK) ─
CREATE TABLE IF NOT EXISTS materials_v2 (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    grade_id TEXT NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Migrate existing rows if any (grade_id will be a placeholder; old data is discarded)
INSERT OR IGNORE INTO materials_v2(id, student_id, grade_id, title, created_at)
    SELECT id, student_id, 'legacy', title, created_at FROM materials;
DROP TABLE materials;
ALTER TABLE materials_v2 RENAME TO materials;
CREATE INDEX IF NOT EXISTS idx_materials_grade ON materials(grade_id, created_at);

-- ─── MaterialFiles ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS material_files (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    upload_type TEXT NOT NULL DEFAULT 'exercise_sheet',
    classified_type TEXT,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    storage_raw_path TEXT NOT NULL,
    storage_md_path TEXT,
    status TEXT NOT NULL DEFAULT 'uploading',
    status_detail TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_material ON material_files(material_id, created_at);
CREATE INDEX IF NOT EXISTS idx_files_student ON material_files(student_id);

-- ─── Question bank ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS question_bank (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES material_files(id) ON DELETE CASCADE,
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    grade_id TEXT NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    q_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    options_json TEXT,
    answer TEXT,
    image_path TEXT,
    table_json TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qbank_file ON question_bank(file_id, order_index);
CREATE INDEX IF NOT EXISTS idx_qbank_material ON question_bank(material_id);

-- ─── Test sessions ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS test_sessions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL REFERENCES material_files(id) ON DELETE CASCADE,
    score INTEGER,
    total INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_test_sessions_file ON test_sessions(file_id);

CREATE TABLE IF NOT EXISTS test_answers (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES question_bank(id) ON DELETE CASCADE,
    student_answer TEXT,
    is_correct INTEGER,
    answered_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_test_answers_session ON test_answers(session_id);

-- ─── App settings ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO app_settings(key, value) VALUES
    ('docling_url', 'http://localhost:5001'),
    ('llm_base_url', 'http://localhost:8321'),
    ('llm_model', 'ollama/qwen2.5:7b-instruct'),
    ('llm_api_key', '');
