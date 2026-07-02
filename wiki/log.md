# Wiki log

Append-only chronological record of every wiki operation. Newest at the top.

Format per entry: date header, **Operation**, **Pages updated**, **Source** (if any), **Cross-refs**, **claude-mem** (if any), key facts.

---

## 2026-06-29 — LiteMaaS kube:admin OAuth login fix; helm chart hardened

- **Operation:** debug + fix + add pitfall
- **Pages updated:**
  - [`pitfalls.md`](pitfalls.md) — entry #28 (`kube:admin` null `oauth_id` on first login)
- **Source:** Live cluster debugging session on `cluster-7hb2t.7hb2t.sandbox670.opentlc.com`, namespace `genai`.
- **Cross-refs:** [`pitfalls.md`](pitfalls.md) ↔ [`helm/litemaas/templates/backend-deployment.yaml`](../helm/litemaas/templates/backend-deployment.yaml)
- **Key facts recorded:**
  - `kube:admin` has no `metadata.uid` in OpenShift — the virtual admin user returns `null` from `/apis/user.openshift.io/v1/users/~`.
  - The `patch-oauth-service` initContainer patches `oauth.service.js` to use `uid || name` as the OAuth subject. It was present in the local chart but had never been deployed (helm release was at revision 1 from June 14; chart updated locally after that).
  - Original script had no `set -e` and no verification — silent failure if pattern not found. Fixed: added `set -e`, `grep -q` pre-check, and exit 1 on failure so a broken patch surfaces as `Init:Error`.
  - Fix deployed via `helm upgrade litemaas helm/litemaas/ -n genai --reuse-values` (revision 2).

---

## 2026-05-23 — student-assistant MVP1 redesign: question bank pipeline

- **Operation:** add findings + add pitfalls
- **Pages updated:**
  - [`findings.md`](findings.md) — new entry "student-assistant MVP1 redesigned: question bank pipeline, no RAG"
  - [`pitfalls.md`](pitfalls.md) — entries #26 (`FloatingActionButton.text` removed in Flet 0.85.1) and #27 (`aiosqlite.executescript` auto-commit breaks migration recording)
- **Source:** Implementation session — complete rewrite of `student-assistant/` from wiki+RAG to question bank architecture.
- **Cross-refs:** [`findings.md`](findings.md) ↔ [`pitfalls.md`](pitfalls.md) ↔ [`../student-assistant/`](../student-assistant/)
- **Key facts recorded:**
  - No RAG, no chat. LlamaStack replaced by generic OpenAI-compatible `AIClient`.
  - New domain: Student → Grade → Material → MaterialFile → QuestionBank → TestSession.
  - Migration v002 idempotent: `CREATE TABLE IF NOT EXISTS materials_v2`.
  - `FloatingActionButton` in Flet 0.85.1 takes no `text=`; use `tooltip=`.
  - `executescript()` auto-commits — never wrap with `BEGIN;`; always record migration after.
  - App starts clean at `http://localhost:8080` via `uv run python app.py`.

---

## 2026-05-16 — student-assistant first local run; Flet 0.85.1 and Podman pitfalls

- **Operation:** add pitfalls + add finding
- **Pages updated:**
  - [`pitfalls.md`](pitfalls.md) — entries #25 (Flet 0.85.1 breaking API changes, 13-item table) and #26 (Podman `host.containers.internal`)
  - [`findings.md`](findings.md) — new dated entry "student-assistant first local run; Flet 0.85.1 compatibility fixes applied"
- **Source:** Live debugging session — iterated on browser session crash traces from `student-assistant/` running under Flet 0.85.1.
- **Cross-refs:** [`pitfalls.md`](pitfalls.md) ↔ [`findings.md`](findings.md) ↔ [`student-assistant/`](../student-assistant/) ↔ [`wiki/handbooks/flet-handbook.md`](handbooks/flet-handbook.md)
- **Key facts recorded:**
  - Flet 0.85.1 (installed by `uv sync`) breaks code written for 0.26 in 13 distinct ways — all fixed in `student-assistant/` as of this date.
  - `flet run --web` crashes with `ModuleNotFoundError: No module named 'flet_desktop'` when only `flet_web` is installed. Use `python app.py` with `ft.app(..., view=ft.AppView.WEB_BROWSER, port=8080)`.
  - `FilePickerFile.path` is always `None` in web mode; must use `pick_files(with_data=True)` and read `.bytes`.
  - `page.session.store` (not `page.session`) is the KV store in 0.85.1. `page.show_dialog()` / `page.pop_dialog()` replace the `page.dialog` assignment pattern.
  - Podman 5.7.1 ships built-in compose (Docker Compose v5.1.0). `host.docker.internal` → `host.containers.internal` in compose files.
  - `.env` must be copied from `.env.example` before first run.
  - Sandbox cluster `ocp.9xgvv.sandbox3434.opentlc.com` DNS expired — needs replacement endpoint.

---

## 2026-05-09 — Wiki tooling ecosystem survey + 3-phase roadmap

- **Operation:** add finding + add roadmap section
- **Pages updated:**
  - [`findings.md`](findings.md) — new dated entry "Wiki tooling ecosystem survey (Karpathy pattern, 2026)"
  - [`future-work.md`](future-work.md) — new section "Wiki tooling roadmap (Karpathy llm-wiki ecosystem)" with three phases
- **Source:** WebSearch + WebFetch across the active 2026 ecosystem of Karpathy-pattern wiki plugins, Obsidian/Logseq MCP servers, and markdown+shadow-vector hybrids. No single canonical source; consolidated links in `findings.md`.
- **Cross-refs:** [`findings.md`](findings.md) ↔ [`future-work.md`](future-work.md) ↔ [`../helm/milvus/`](../helm/milvus/) (memsearch dogfooding angle).
- **Key facts recorded:**
  - At least 5 active Claude Code plugins/skills implement Karpathy's pattern: `kfchou/wiki-skills`, `Astro-Han/karpathy-llm-wiki`, `ussumant/llm-wiki-compiler`, `nvk/llm-wiki`, `praneybehl-llm-wiki`. Most feature-rich is `llm-wiki-compiler` (coverage tags, time-decay warnings, `/wiki-visualize`).
  - `zilliztech/memsearch` is a markdown+Milvus shadow-index pattern — markdown source of truth, Milvus rebuildable cache, hybrid BM25+dense+RRF. Strong fit for this project because we already deploy Milvus via [`helm/milvus/`](../helm/milvus/) — can dogfood the customer-facing vector store.
  - Obsidian-shaped MCP servers (`jacksteamdev/obsidian-mcp-tools`, `aaronsb/obsidian-semantic-mcp`) read plain markdown directories, no Obsidian app required. Defer until wiki crosses ~50 pages.
  - Managed memory services (Mem0, Zep, Letta, Cognee, Cloudflare Agent Memory) are explicitly skipped — they pull the wiki off git, forfeiting auditability and PR-reviewability.
- **Recommendation captured in `future-work.md`:** Phase 1 (`llm-wiki-compiler` skill) is high-value/low-cost — install. Phase 2 (`memsearch` against existing Milvus) is medium-value/medium-cost — defer until wiki grows or a Milvus debugging need surfaces. Phase 3 (Obsidian MCP) is overbuilt for current corpus size.

---

## 2026-05-09 — Bootstrap the wiki

- **Operation:** create wiki root, migrate existing docs
- **Pages created:** [`README.md`](README.md), [`architecture.md`](architecture.md), [`components.md`](components.md), [`findings.md`](findings.md), [`runbook.md`](runbook.md), [`SOURCES.md`](SOURCES.md), [`log.md`](log.md)
- **Pages migrated** (via `git mv`, history preserved):
  - `llama-stack-ui/docs/decisions.md` → [`decisions.md`](decisions.md)
  - `llama-stack-ui/docs/entanglements.md` → [`entanglements.md`](entanglements.md)
  - `llama-stack-ui/docs/future-work.md` → [`future-work.md`](future-work.md)
  - `llama-stack-ui/docs/guardrails-redteam-report.md` → [`guardrails-redteam-report.md`](guardrails-redteam-report.md)
  - `llama-stack-ui/docs/llama-stack-api-improvements.md` → [`llama-stack-api-improvements.md`](llama-stack-api-improvements.md)
  - `llama-stack-ui/docs/model-benchmarks.md` → [`model-benchmarks.md`](model-benchmarks.md)
  - `llama-stack-ui/docs/pitfalls.md` → [`pitfalls.md`](pitfalls.md)
  - `docs/flet-handbook.md` → [`handbooks/flet-handbook.md`](handbooks/flet-handbook.md)
  - `docs/llamastack-handbook.md` → [`handbooks/llamastack-handbook.md`](handbooks/llamastack-handbook.md)
- **Tooling added:** [`../scripts/wiki_lint.py`](../scripts/wiki_lint.py) — mechanical checks for broken links, orphan pages, source frontmatter, log date monotonicity.
- **CLAUDE.md change:** Replaced the small "Wiki / Persistent Knowledge" section with a full Karpathy-style "Local wiki discipline" section — read order, write order, rules. The wiki path moved from `llama-stack-ui/docs/` to `wiki/`.
- **Source:** Karpathy gist [llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and the agentic-ivr `wiki/` precedent.
- **claude-mem:** #893, #896, #898, #902 — design discovery and 5-phase plan.
- **Key facts recorded:**
  - Single wiki root at `wiki/`, not split across multiple dirs.
  - `findings.md` and `runbook.md` are NEW pages — they did not exist in the legacy `llama-stack-ui/docs/` layout. Future sessions should populate them as work happens, rather than retroactively backfilling.
  - `sources/` and `entities/` directories created empty — no retroactive seeding (the raw materials for `flet-handbook.md` and `llamastack-handbook.md` are gone).
  - `log.md` and claude-mem are complementary: this log is in-repo and survives history; claude-mem is conversational and survives compaction. A `log.md` entry may reference a claude-mem ID (e.g. `#902`) to give future readers a way back to the conversation.
