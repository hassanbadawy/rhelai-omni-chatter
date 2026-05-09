# Wiki log

Append-only chronological record of every wiki operation. Newest at the top.

Format per entry: date header, **Operation**, **Pages updated**, **Source** (if any), **Cross-refs**, **claude-mem** (if any), key facts.

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
