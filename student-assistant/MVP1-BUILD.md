# MVP1 Build Guide

Detailed implementation plan for MVP1 of the Student Assistant. Hand this to a code-generating agent (or follow yourself). Every file referenced is already scaffolded in this directory — modules have docstrings + signatures + `NotImplementedError` placeholders. Your job is to fill in the bodies, in the order described below.

## What MVP1 ships

- Single hard-coded student row (`student-mvp1`).
- Flat list of materials (no subjects).
- Upload PDF → Docling → markdown → LLM-compiled wiki → chapter-split files → chat.
- Chat uses **wiki + chapter-loading retrieval**. No Milvus, no embeddings, no chunking.
- One Flet desktop window. Two routes: `/` and `/material/{id}`.
- Background asyncio JobWorker handles parse/wiki/split off the UI thread.

## What MVP1 does NOT ship

Auth, profiles, subjects, settings, quizzes, flashcards, mastery, streaks, dashboard, types 2/3/4, embeddings, Milvus, image-as-exercise, COPPA, notifications, weekly summaries, retention purge, accessibility polish, multilingual UI.

These are MVP2–5. Don't build them now.

## Architecture overview

```
┌──────────────────────────────────────────────────────────────┐
│  Flet app (single Python process)                           │
│    ├─ views/  — pages: materials_list, material_detail,     │
│    │            chat_tab, wiki_tab; upload_modal             │
│    ├─ services/ — storage(SQLite), object_store(local FS),  │
│    │              docling, llama_stack, jobs, ingest         │
│    └─ workers/ — parse_document, compile_wiki, split_chapters│
└────────┬─────────────────────────────────────────┬──────────┘
         │ HTTP                                     │ HTTP
         ▼                                          ▼
       Docling                                 Llama Stack
       :5001                                   :8321
                                                    │
                                                    ▼
                                                Ollama (or any
                                                OpenAI-compat LLM)
```

No Milvus. No vector store. Chapter-loading retrieval = LLM picks chapter id(s) from the wiki overview, the app loads those chapter md files, sends them to the LLM as context.

## Build order (the only order that minimizes rework)

1. **Skeleton & migrations** — `cli.py migrate` works against a fresh sqlite. `pyproject.toml`, `config.py`, `migrations/v001_mvp1.sql`. Verify with `uv run student-assistant migrate`.
2. **Domain layer** — fill in `domain/models.py`, `domain/enums.py`, `domain/schemas.py`. No I/O. Add `tests/test_schemas.py` for `WikiFrontmatter` validation.
3. **Storage** — `services/storage.py`. Apply migration, expose CRUD for `materials`, `chat_sessions`, `chat_messages`. Run `tests/test_storage.py`.
4. **Object store** — `services/object_store.py`. Local FS only. Path helpers + read/write text/bytes.
5. **Job system** — `services/jobs.py`. `Jobs` (enqueue/claim/complete/fail) + `JobWorker` (asyncio loop). Use `BEGIN IMMEDIATE` for the claim transaction. **Test idempotency** — re-claiming after crash must not double-run.
6. **External clients** — `services/docling.py` (one POST call) and `services/llama_stack.py` (chat_completions + chat_completions_stream). Use `httpx.AsyncClient` with timeouts. **Don't** wire SSE parsing the wrong way — the stream returns `data: {...}\n\n` events; emit `delta.content` from each.
7. **Ingest pipeline** — `ingest/wiki_compiler.py` (build_prompt + parse_response) and `ingest/chapter_splitter.py` (page-marker scanning + slicing). Pure functions, easy to test. Run `tests/test_wiki_compiler.py` and `tests/test_chapter_splitter.py`.
8. **Workers** — fill in handlers in this order: `parse_document` → `compile_wiki` → `split_chapters` → `ingest_material` (parent). Each must be idempotent (skip-if-already-done). `workers/registry.py` is already wired.
9. **Ingest service** — `services/ingest.py` `submit_upload` (insert row → save bytes → enqueue parent job → return material).
10. **App entry + JobWorker startup** — `app.py main()` constructs the dependency container, starts the JobWorker as an asyncio task, mounts initial route.
11. **UI: materials list** — `views/materials_list.py` + `widgets/material_card.py` + `views/upload_modal.py`. End-to-end: pick PDF → status flips through stages → card updates live.
12. **UI: material detail + Wiki tab** — `views/material_detail.py` + `views/wiki_tab.py`. Read `wiki.md`, render frontmatter as a structured panel + body markdown.
13. **UI: Chat tab** — `views/chat_tab.py` + `widgets/streaming_bubble.py`. Implement the chapter-loading flow: router LLM call → load chapter md files → answer LLM call → stream tokens → persist with citations_json.
14. **E2E tests** — `tests/test_ingest_pipeline_e2e.py`. Set `STUDENT_ASSISTANT_E2E=1` and run against the Docker Compose stack.

## Key implementation rules

- **Async everywhere.** Every service method, every worker handler, every Flet event handler. Never block the UI thread.
- **Idempotency every job.** Check "is the output already there?" before running. SHA-256 dedupe where applicable.
- **Status transitions are the contract.** `materials.status` is the single source of truth for ingest progress. Every worker writes to it in a transaction with its other side-effects.
- **Pubsub for live UI updates.** When a worker updates `material.status`, publish to `Page.pubsub` with topic `material:{id}`. Views subscribe and re-render. No polling.
- **Validation at boundaries.** Trust internal callers; validate at the boundary with external systems (Docling response, LLM response, file picker input).
- **Quote exact strings.** SQL strings, error messages, env var names — keep them in code as constants where another agent can grep for them.
- **No premature abstraction.** Don't build a generic retrieval interface in MVP1 — chapter-loading is the only retrieval and it's narrow. MVP2 introduces a `Retriever` protocol when there's a second implementation.

## Chat flow (chapter-loading retrieval)

The single most important piece of MVP1. Implement carefully:

```python
# Pseudo-code for views/chat_tab.py on send-message
async def send_message(material_id: str, user_text: str) -> None:
    # 1. Append user message to chat_messages
    await storage.append_chat_message(...)

    # 2. Load wiki frontmatter (parse YAML from wiki.md)
    wiki = await load_wiki_frontmatter(material_id)

    # 3. Pick chapters via LLM router (skip if only 1 chapter)
    if len(wiki.chapters) == 1:
        chapter_ids = [wiki.chapters[0].id]
    else:
        chapter_ids = await route_question_to_chapters(wiki, user_text)
        # Router prompt: send wiki overview (chapters + synthesis) + question,
        # ask for JSON {"chapter_ids": ["ch1", "ch3"]}. Limit to top 2-3.

    # 4. Load chapter md from disk
    chapter_md = []
    for cid in chapter_ids:
        chapter_md.append(await object_store.read_text(chapters_dir / f"{cid}.md"))

    # 5. Build messages and stream answer
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": f"<wiki>\n{wiki_overview}\n</wiki>\n\n<chapters>\n{chr(10).join(chapter_md)}\n</chapters>\n\nQuestion: {user_text}"},
        # ... plus recent chat history
    ]

    bubble = StreamingBubble()
    async for token in llama_stack.chat_completions_stream(messages, model=cfg.llm_model):
        await bubble.append_token(token)

    # 6. Persist assistant message with citations
    await storage.append_chat_message(
        ...,
        content=bubble.finalize(),
        citations_json=json.dumps([
            {"chapter_id": c.id, "chapter_title": c.title, "page_range": c.page_range}
            for c in wiki.chapters if c.id in chapter_ids
        ]),
    )
```

Two LLM calls per message (router + answer). For materials with one chapter, skip the router. If chapter_md exceeds the LLM's context window, truncate the oldest chapter and warn in the response (this is a known MVP1 limitation; MVP2's chunk RAG fixes it).

## Wiki compile prompt — the most failure-prone part

`compile_wiki` calls the LLM with a system prompt that demands strict YAML frontmatter. LLMs are bad at strict YAML on the first try. Mitigations:

1. **Validate every response.** Reject and retry up to 3 times if the YAML doesn't parse or the schema fails.
2. **Pin a strong model.** Don't try this with a 1B model. Qwen2.5-7B-Instruct is the floor.
3. **Keep the schema small.** MVP1 only requires `material_id`, `chapters[]`, `synthesis`. Leave `exercises[]`, `figures[]`, `key_terms[]` empty if the model wants — they're populated by MVP3+ jobs.
4. **Truncation handling.** If the document is >60K chars, send a sliding window and merge chapter lists by `page_range`. Document the merge logic when you write it.

## "Done when" — exit criteria for MVP1

Run these in order; each must pass before MVP2 work starts.

1. `uv run student-assistant migrate` initializes a fresh sqlite at `~/.student-assistant/db.sqlite3` and exits 0.
2. `uv run student-assistant doctor` reports `Llama Stack: ok | Docling: ok | DB: v1` against the running Docker Compose stack.
3. Upload a 50-page PDF via the UI. Status flips `uploading → converting → indexing → ready` in <5 min.
4. `wiki.md` is on disk under `~/.student-assistant/storage/md/student-mvp1/{material_id}/wiki.md` with a parseable YAML frontmatter that contains at least one chapter.
5. `chapters/` directory under that material has one .md file per chapter.
6. The Wiki tab renders the chapter list and synthesis paragraph.
7. The Chat tab streams a coherent answer to "summarize chapter 2" with citations referencing chapter 2.
8. Quit the app mid-ingest of a second material. Restart. The ingest resumes from the last completed stage (no double-runs of completed children, no orphaned `running` rows).
9. `pytest tests/` passes. The E2E test (`STUDENT_ASSISTANT_E2E=1`) passes against the Compose stack.

## Pitfalls to expect (don't waste time rediscovering)

- **`flet run` and asyncio:** Flet wraps the event loop; asyncio tasks started from `main()` work fine, but `run_until_complete` will fight Flet. Use `asyncio.create_task` only.
- **SQLite + asyncio:** `aiosqlite` is the right binding. WAL mode is mandatory if any writer concurrency exists; v001_mvp1.sql sets it.
- **Docling response shape:** The `image_export_mode: embed` flag means the markdown contains base64 image blocks. Don't ship them through the LLM prompt — strip image blocks before sending to `compile_wiki`. Re-attach for the Wiki tab render.
- **LLM context window:** Qwen2.5-7B is 32K tokens, ~25K usable after system prompt. A 50-page PDF in markdown is ~30K tokens — borderline. Truncate aggressively in `compile_wiki` (via sliding window) but for chat-time chapter loading, only one or two chapters fit, which is fine.
- **Docker Compose `host.docker.internal`:** On Linux this needs `extra_hosts: ["host.docker.internal:host-gateway"]` (already set in our compose file). Mac & Windows resolve it natively.
- **SSE parsing:** Llama Stack returns text/event-stream with `data: {...}\n\n` events terminated by `data: [DONE]`. Use `httpx.AsyncClient.stream` and split on `\n\n`. Don't try a JSON-streaming parser; SSE is line-based.

## After MVP1

When all 9 exit criteria pass, commit and tag `mvp1`. Then:

1. Read `~/.claude/plans/student-assistant-architecture.md` section 2 "MVP2".
2. Add `subjects` table + UI (write `migrations/v002_mvp2_subjects.sql`).
3. Add `chunk_and_embed` job kind (write `workers/chunk_and_embed.py`, register in `workers/registry.py`).
4. Add Milvus Lite to `docker-compose.yml` and the Llama Stack env.
5. Extend chat to hybrid retrieval (wiki + chunks via RRF).

Do not refactor MVP1 code to make MVP2 fit. MVP1's modules are already shaped for MVP2 to extend (the `Retriever` interface added in MVP2 will wrap MVP1's chapter-loader as one implementation alongside the new vector retriever).
