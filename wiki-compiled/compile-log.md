# Wiki Compile Log

Append-only log of every `/wiki-compile` run.

## 2026-05-09 — Initial compilation

**Topics created (8):** llama-stack-platform, guardrails-and-safety, streamlit-playground-ui, models-and-inference, rag-and-vector-store, deployment-and-ops, flet-framework, future-work-roadmap.

**Concepts created (3):** two-image-schema-fork, wrapping-upstream-where-broken, helm-upgrade-staleness.

**Sources scanned:** 15 (16 total in `wiki/` minus the excluded `log.md`). All treated as new on first run.

**Topic article sizes:**
- llama-stack-platform.md — 217 lines (8 sources)
- guardrails-and-safety.md — 370 lines (6 sources)
- streamlit-playground-ui.md — 126 lines (6 sources)
- models-and-inference.md — 254 lines (5 sources)
- rag-and-vector-store.md — 186 lines (5 sources)
- deployment-and-ops.md — 251 lines (4 sources)
- flet-framework.md — 414 lines (1 source — handbook)
- future-work-roadmap.md — 71 lines (2 sources)

**Coverage tags:** Most sections landed at `[coverage: high]` because the source corpus is dense and well-curated. Two notable exceptions: flet-framework is `[coverage: low -- 1 source]` across the board (only the handbook contributed, even though it's comprehensive), and rag-and-vector-store's Findings & Measurements is `[coverage: low]` (no RAG-specific benchmarks captured yet — flagged as a gap for future work).

**Schema generation:** First-run schema written to `schema.md` with all 8 topic slugs + aliases and 3 concept slugs.

**Mode:** staging — the compiled wiki sits beside the hand-curated `wiki/`. No CLAUDE.md modifications.

**Notes for next compile:**
- The hand-curated `wiki/findings.md` will accumulate dated entries between runs — they need to flow into the Findings & Measurements sections of the relevant topic articles on each compile.
- The Decisions & Rationale of `rag-and-vector-store` was assembled from `architecture.md` + `components.md` + `pitfalls.md` because `decisions.md` has no dedicated RAG entry. If a future RAG-specific decision is recorded, the topic article should re-pull it.
- Some future work items will date-decay; the time-decay rule kicks in at >18 months, so revisit annually.
