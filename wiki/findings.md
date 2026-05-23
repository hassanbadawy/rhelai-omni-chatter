# Findings

Empirical results, dated, in chronological order. Newest at the top. Each finding has a date, a one-line headline, and the smallest set of facts a future Claude needs to act on it.

When a finding is later overturned, **append a correction with a new date** and link to the old entry. Never edit or delete the old entry.

---

## 2026-05-09 — Wiki tooling ecosystem survey (Karpathy pattern, 2026)

The Karpathy llm-wiki gist (April 2026) has produced a small but active tooling ecosystem. The cons of the pure-markdown wiki pattern — manual curation cost, no fuzzy match, rot, scale — are mostly addressed by drop-in tools that keep markdown as the source of truth and add mechanical helpers around it. Survey of what exists as of 2026-05-09:

**Claude Code skills/plugins** (closest fit, install over our existing `wiki/`):
- [`ussumant/llm-wiki-compiler`](https://github.com/ussumant/llm-wiki-compiler) — most feature-rich. Provides `/wiki-compile`, `/wiki-capture`, `/wiki-ingest`, `/wiki-search`, `/wiki-lint`, `/wiki-query`, `/wiki-visualize` (knowledge graph view). Adds **coverage tags** (`[coverage: high -- 15 sources]`) and **time-decay warnings** (⚠️ on claims >18 months) — both directly attack wiki rot.
- [`kfchou/wiki-skills`](https://github.com/kfchou/wiki-skills) — `/wiki-init`, `/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-update`, `/wiki-audit`. The `/wiki-audit` per-page citation verification is the closest analogue to our `sources/` discipline.
- [`Astro-Han/karpathy-llm-wiki`](https://github.com/Astro-Han/karpathy-llm-wiki) — single SKILL.md, multi-tool compatible (Claude Code, Cursor, Codex).
- [`nvk/llm-wiki`](https://github.com/nvk/llm-wiki) — multi-agent parallel research (5–10 agents), thesis-driven investigation. Best for *autonomously growing* the wiki rather than hand-curating.

**MCP servers for markdown vaults** (cross-tool access without leaving markdown):
- [`jacksteamdev/obsidian-mcp-tools`](https://github.com/jacksteamdev/obsidian-mcp-tools) — semantic search + Templater.
- [`aaronsb/obsidian-semantic-mcp`](https://github.com/aaronsb/obsidian-semantic-mcp) — collapses 21+ tools into 5 AI-optimized ops.
- [`MarkusPfundstein/mcp-obsidian`](https://github.com/MarkusPfundstein/mcp-obsidian) — canonical Obsidian REST integration.

**Markdown + shadow vector index** (RAG-without-RAG-architecture):
- [`zilliztech/memsearch`](https://github.com/zilliztech/memsearch) — **strong fit for this project**. Markdown is source of truth; Milvus is a "shadow index" — derived, rebuildable cache. Hybrid BM25 + dense + RRF reranking. SHA-256 dedup. Live file watching. We already deploy Milvus via [`helm/milvus/`](../helm/milvus/) — pointing memsearch at the same Milvus would dogfood the customer-facing vector store. Install: `/plugin marketplace add zilliztech/memsearch`.

**Managed memory services** (Mem0, Zep, Letta, Cognee, Cloudflare Agent Memory) — pull you off git-versioned markdown. Skipping these for this project; auditability and PR-reviewability are non-negotiable.

**Action:** see [`future-work.md`](future-work.md) "Wiki tooling roadmap" for the staged adoption plan. Phase 1 (`llm-wiki-compiler`) is the highest-leverage drop-in; Phase 2 (`memsearch` against existing Milvus) is the dogfooding play.

---

## 2026-05-09 — Wiki bootstrap

The legacy `llama-stack-ui/docs/` and `docs/` were merged into `wiki/`. `findings.md` is a new page; pre-existing dated observations live in [`pitfalls.md`](pitfalls.md), [`decisions.md`](decisions.md), and [`model-benchmarks.md`](model-benchmarks.md). This page collects new dated observations going forward — performance numbers, integration tests, surprising behaviors, regressions.

Use this page when the observation is **dated and empirical**. Use [`pitfalls.md`](pitfalls.md) when the observation is **a bug with a root cause and fix**. Use [`decisions.md`](decisions.md) when the observation is **a deliberate choice with rationale**.

---

## 2026-05-09 — LiteLLM TLS chain works end-to-end (claude-mem #813)

Full `llama-stack → LiteLLM → vLLM/KServe` chain is verified working on the `agentic-ivr` cluster after fixing TLS trust on LiteLLM. The fix:

- Add an `initContainer` to LiteLLM that combines the OpenShift service-CA bundle with the system CA bundle into a single PEM file and mounts it at `/etc/ssl/certs/ca-bundle.crt`.
- Set `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and `CURL_CA_BUNDLE` to that path.
- LiteLLM's main container then trusts the in-cluster `*.svc` certificates issued by the OpenShift service-CA.

Without this, LiteLLM rejected the vLLM KServe predictor's self-signed cert and `llama-stack` saw a `500 Connection error`. Direct `llama-stack → vLLM` worked because llama-stack already had `tls_verify: false` set on the vLLM provider — but routing through LiteLLM made `tls_verify: false` insufficient because the failure was now between LiteLLM and vLLM, where llama-stack has no say.

Commit: `3770ba6` ("Fix LiteMaaS SSO and trust OpenShift service-CA in LiteLLM").

## 2026-05-09 — Guardrails red-team: language_detection always trips on English greetings

Documented in [`guardrails-redteam-report.md`](guardrails-redteam-report.md). The `papluca/xlm-roberta-base-language-detection` model classifies short English greetings (`hi`, `hey, how are you`) as non-English at >0.9 confidence. With `confidence_threshold: 0.85`, every greeting is blocked.

Mitigations (pick one):

1. Drop the `language_detection` shield from `output_shields` if you want unblocked greetings.
2. Raise threshold to ≥0.99.
3. Skip the shield client-side for messages under N tokens.

The model is fine on full sentences — the issue is short utterance ambiguity.

## 2026-05-09 — Fictional/hypothetical framing is the only full-stack guardrails bypass

11-attack adversarial suite against the four shields: HAP, prompt_injection, language_detection, regex. Only the "fictional emergency" framing (e.g. *"In a story I'm writing, a character needs to ..."*) bypassed all four shields AND elicited the protected response from the LLM.

This is consistent with the broader prompt-injection literature: detectors trained on direct injections do not catch indirection through fictional framing, because the surface tokens look like creative writing.

Mitigations are model-side, not shield-side: tighter system prompt, refuse-to-roleplay clauses, separate output-classifier on the response.

See [`guardrails-redteam-report.md`](guardrails-redteam-report.md) "Attack 7" and 10 for details.

---

## 2026-05-23 — student-assistant MVP1 redesigned: question bank pipeline, no RAG

Full redesign of `student-assistant/` from a wiki+RAG chat app into a question bank + test runner. The app now supports multiple students and a Student → Grade → Material → File hierarchy. Key facts:

- **No RAG, no chat.** The LlamaStack dependency is gone. Any OpenAI-compatible endpoint (vLLM, Ollama, OpenRouter, LMStudio, MaaS) is configured in the Settings UI and stored in the `app_settings` SQLite table — no restart needed.
- **Pipeline:** Upload → Docling (MD) → LLM classify (`chapter_data` | `exercise_sheet`) → LLM extract questions → `question_bank` table.
- **Question types:** `mcq`, `text_qna`, `true_or_false`, `image_qna`, `table_comparison`. Images extracted from Docling base64 inline refs, saved to disk, path stored in `image_path`.
- **Test runner:** one-question-at-a-time quiz with auto-scoring (`student_answer.strip().lower() == answer.strip().lower()`).
- **Migration:** `v002_redesign.sql` — drops `chat_messages`/`chat_sessions`, rebuilds `materials` with `grade_id`, adds `grades`, `material_files`, `question_bank`, `test_sessions`, `test_answers`, `app_settings`. Uses `CREATE TABLE IF NOT EXISTS materials_v2` (idempotent).
- **Flet pitfalls found:** `FloatingActionButton` does not accept `text=` in 0.85.1 (use `tooltip=`); `aiosqlite.executescript()` auto-commits before running (see [`pitfalls.md` #27](pitfalls.md)).
- App serves at `http://localhost:8080` — run with `uv run python app.py`.

---

## 2026-05-16 — student-assistant first local run; Flet 0.85.1 compatibility fixes applied

The student-assistant MVP1 app was started locally for the first time using `podman compose up -d` + `uv run python app.py`. The app was written against Flet 0.26 but `uv sync` installs 0.85.1, which has ~13 breaking API changes. All were found and fixed by iterating on browser session crash traces. The app now serves cleanly at `http://localhost:8080` with zero session errors.

Key operational notes:
- `.env` must be created from `.env.example` before first run — the app raises `RuntimeError: Missing required environment variable(s)` without it.
- `flet run --web` CLI path is broken when only `flet_web` is installed (imports `flet_desktop` unconditionally). Correct launch: `python app.py` with `view=ft.AppView.WEB_BROWSER` in `_run()`.
- Sandbox cluster `ocp.9xgvv.sandbox3434.opentlc.com` DNS no longer resolves — expired. `.env` needs updating to a live endpoint before upload/chat can be tested end-to-end.

See [`pitfalls.md` #25](pitfalls.md) for the complete Flet API change table and [`pitfalls.md` #26](pitfalls.md) for the Podman `host.containers.internal` fix.

---

## How to add an entry

```markdown
## YYYY-MM-DD — One-line headline

(2-6 sentences of context. What was tested, what happened, exact error or measurement, the file path or URL involved. End with the action a future reader should take, or the cross-link to the page that has the full story.)

(Optional: commit SHA, claude-mem ID, links to related findings.)
```

Keep entries small. If a finding grows beyond ~10 lines, give it its own topic page and reference it from here.
