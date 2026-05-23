# Student Assistant

AI study assistant. Upload a PDF, get a wiki, chat with it.

This directory holds the working code. The full architecture spec lives at `~/.claude/plans/student-assistant-architecture.md`. The detailed MVP1 build plan lives at [`MVP1-BUILD.md`](MVP1-BUILD.md).

## What's here (MVP1)

- Single user (hard-coded), flat list of materials, per-material chat.
- Upload a PDF → Docling converts to markdown → LLM compiles a structural wiki → chat reads the wiki + chapter-relevant pages and answers with citations.
- **No Milvus, no embeddings, no auth.** That's MVP2 and MVP4.

## Quick start (MVP1)

```bash
# 1. Bring up Llama Stack + Docling + Ollama (the only external services MVP1 needs)
docker compose up -d
ollama pull qwen2.5:7b-instruct          # or your preferred OpenAI-compatible model

# 2. Set up the Python env
cp .env.example .env                      # then edit .env
uv sync

# 3. Initialize the SQLite DB
uv run student-assistant migrate

# 4. Run the app
uv run flet run app.py
```

The app opens a desktop window. Upload a PDF, wait for ingest to finish (status flips through `uploading → converting → indexing → ready`), open the material, and chat.

## Project layout

See the layout in [`MVP1-BUILD.md`](MVP1-BUILD.md). At a glance:

```
student-assistant/
├── app.py                 Flet entry, route handler, JobWorker task
├── config.py              .env loader
├── cli.py                 `student-assistant migrate` command
├── views/                 Flet pages (materials list, material detail, chat tab, wiki tab)
├── services/              storage, object_store, docling, llama_stack, jobs, ingest
├── workers/               one handler per job kind (ingest_material, parse_document, ...)
├── ingest/                wiki_compiler, chapter_splitter
├── domain/                models, enums, schemas (Pydantic)
├── widgets/               Flet custom controls
├── migrations/            v001_mvp1.sql
└── tests/
```

## Status

**MVP1 — in progress.** Track milestone exit criteria in [`MVP1-BUILD.md`](MVP1-BUILD.md) "Done when" section.

## Future MVPs

- **MVP2:** add subjects + chunking + Milvus + hybrid retrieval (granular Q&A)
- **MVP3:** all 4 material types, question bank, quizzes, flashcards, mastery, streaks
- **MVP4:** signup/signin, profile, multi-student, COPPA
- **MVP5:** full v1 spec — every cron, every setting, accessibility, GDPR export

Each MVP is additive — never replaces earlier code. Full progression in `~/.claude/plans/student-assistant-architecture.md` section 2.
