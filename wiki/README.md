# rhelai-omni-chatter wiki

This is the persistent memory of the project. It is append-mostly, cross-referenced markdown that accumulates findings across sessions. Treat it as the source of truth, not a side artefact.

Modeled on Karpathy's [llm-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Read order — always wiki first

Before answering any question or writing any code about this project, follow this order:

1. **[`README.md`](README.md)** (this file) — orient.
2. **[`architecture.md`](architecture.md)** — layered design (UI → Llama Stack → vLLM/Guardrails/Milvus).
3. **[`components.md`](components.md)** — per-component rationale, current cluster URLs, model choices, helm chart status, license notes.
4. **[`findings.md`](findings.md)** — empirical results, dated, in chronological order. Many "obvious" answers are already here with a date and a why.
5. **[`runbook.md`](runbook.md)** — operational recipes (deploy guardrails, register a model, debug TLS, file a release).
6. **[`decisions.md`](decisions.md)** — architectural decisions with rationale (Chat Completions vs Responses API, client-side history, etc.).
7. **[`pitfalls.md`](pitfalls.md)** — bug log with root cause and fix for every non-obvious bug hit so far.
8. **[`log.md`](log.md)** — append-only chronological record of every wiki operation.
9. Topic pages and entities (see categories below).

Only fall back to reading raw source (helm values, manifests, Streamlit code) if the wiki does not have the answer.

## Topics

### Streamlit UI internals
- [`entanglements.md`](entanglements.md) — cross-file dependency map: session state keys, config.yaml consumers, api.py↔chat.py contract, dead code inventory.
- [`llama-stack-api-improvements.md`](llama-stack-api-improvements.md) — future improvement opportunities across the Llama Stack API surface.

### Performance
- [`model-benchmarks.md`](model-benchmarks.md) — measured latency/throughput per model with per-use-case recommendations (voice agent, chat, RAG, agent/tool-using).

### Safety
- [`guardrails-redteam-report.md`](guardrails-redteam-report.md) — red-team test report across the four shields, with bypass cases.

### Roadmap
- [`future-work.md`](future-work.md) — ideas explored but not implemented (GitOps via ArgoCD, fresh-cluster bootstrap, llm-d distributed inference).

### Reference handbooks
- [`handbooks/llamastack-handbook.md`](handbooks/llamastack-handbook.md) — zero-to-hero Llama Stack: APIs, providers, agents, RAG, MCP, guardrails, telemetry.
- [`handbooks/flet-handbook.md`](handbooks/flet-handbook.md) — zero-to-hero Flet: controls, navigation, packaging, services architecture.

### Raw research artefacts
- [`sources/`](sources/) — immutable web fetches, transcripts, benchmark CSVs. Naming: `YYYY-MM-DD-slug.md`. See [`SOURCES.md`](SOURCES.md) for the frontmatter contract.

### Single-concept pages
- [`entities/`](entities/) — one page per concept (one model, one CRD, one operator). Empty until a topic deserves its own page.

## Write order — every non-trivial finding must be persisted

When you discover, decide, fix, or measure anything that a future Claude session would need to know, you **must** update the wiki before considering the task done.

1. **Pick the right page.** Empirical result with a date → `findings.md`. New runtime/model component or rationale change → `components.md`. New operational recipe → `runbook.md`. Architectural decision → `decisions.md`. New bug with a root cause → `pitfalls.md`. New topic that doesn't fit any existing page → create a new page in `wiki/`.
2. **Update the page in place.** Keep dated entries; do not silently rewrite history. New entries go at the top (or in the chronological position called for by the page convention).
3. **Append an entry to [`log.md`](log.md)** describing what was ingested, which pages were updated, the source, and the key facts. The log is append-only; never edit prior entries.
4. **Cross-link.** If the new content references another page, link to it (`pitfalls.md` ↔ `decisions.md` ↔ `components.md` etc.). The graph matters as much as the nodes.

## Karpathy-style rules

- **Persist, don't answer in place.** When a session uncovers a fact, write it into the wiki first, then answer the user from the wiki. The wiki is what survives compaction; the chat does not.
- **Date everything.** Every finding gets the day it was observed. Stale claims are obvious only if they're dated.
- **One page per topic, additively edited.** Don't create `findings_v2.md`. Don't fork a page when you can append a dated entry.
- **Quote the source.** Cluster URL, file path, error message verbatim, command output, exact YAML stanza. Future Claude needs the exact string to grep for.
- **Record failure as well as success.** "We tried X and it failed because Y" is among the highest-value content. The Gemma 3n empty-output finding and the `remote::passthrough`-vs-IBM-detectors mismatch are canonical examples.
- **Cross-link aggressively.** A finding without a link to the related component or runbook entry is half-finished.
- **No silent rewrites.** If a prior wiki entry turns out to be wrong, append a correction with a date and link to the prior entry; do not edit the prior entry to make it look right.
- **The log is the audit trail.** Anyone reading [`log.md`](log.md) top-to-bottom should be able to reconstruct the project's evolution.

## Lint

`scripts/wiki_lint.py` runs mechanical checks: broken internal links, orphan pages (on disk but not in this README), unindexed pages (linked here but missing on disk), `sources/` frontmatter completeness, `log.md` date monotonicity. Run on demand:

```bash
python3 scripts/wiki_lint.py
```

Semantic checks (does this page actually belong here? is the categorization right?) are not automated — review quarterly.
