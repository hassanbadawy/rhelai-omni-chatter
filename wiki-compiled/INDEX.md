# rhelai-omni-chatter Knowledge Base

Last compiled: 2026-05-09
Total topics: 8 | Total concepts: 3 | Total sources: 16 markdown files (`wiki/` + `wiki/handbooks/`)

> **Mode**: staging — this compiled wiki sits beside the hand-curated [`../wiki/`](../wiki/). The hand-curated wiki remains the source of truth; this is a derived view organized by reader-intent topic clusters with cross-cutting concept articles.

## How to use this wiki

1. **Start here.** Scan the topic table to find the area you care about.
2. **Read 1–3 topic articles** relevant to your task. Coverage tags tell you whether to trust the section or fall back to raw sources.
3. **Browse [`concepts/`](concepts/)** for cross-cutting patterns that span multiple topics.
4. **Fall back to raw sources** in [`../wiki/`](../wiki/) when a section is `[coverage: low]` or you need exact verbatim content.

Coverage tags on each section:
- `[coverage: high -- N sources]` — trust this section.
- `[coverage: medium -- N sources]` — good overview; check raw sources for detail.
- `[coverage: low -- N sources]` — read the raw sources directly; this section is sparse.

## Topics

| Topic | Aliases | Sources | Last Updated | Status |
|---|---|---|---|---|
| [llama-stack-platform](topics/llama-stack-platform.md) | llama-stack, llamastack, orchestration | 8 | 2026-05-09 | active |
| [guardrails-and-safety](topics/guardrails-and-safety.md) | guardrails, shields, trusty_fms, hap, prompt-injection, fms | 6 | 2026-05-09 | active |
| [streamlit-playground-ui](topics/streamlit-playground-ui.md) | ui, streamlit, playground, llama-stack-ui | 6 | 2026-05-09 | active |
| [models-and-inference](topics/models-and-inference.md) | vllm, models, qwen, gpt-oss, gemma, embeddings, inference | 5 | 2026-05-09 | active |
| [rag-and-vector-store](topics/rag-and-vector-store.md) | rag, milvus, vector-store, embeddings, retrieval | 5 | 2026-05-09 | active |
| [deployment-and-ops](topics/deployment-and-ops.md) | helm, deploy, ops, openshift, runbook | 4 | 2026-05-09 | active |
| [flet-framework](topics/flet-framework.md) | flet, ui-framework, mobile, cross-platform | 1 | 2026-05-09 | active |
| [future-work-roadmap](topics/future-work-roadmap.md) | future, roadmap, argocd, llm-d, gitops, wiki-tooling | 2 | 2026-05-09 | active |

## Concepts

Cross-cutting patterns that appear across multiple topics. Read these for the synthesis — they answer "what does this pattern mean?" rather than just "what happened?".

| Concept | Connects | Last Updated |
|---|---|---|
| [two-image-schema-fork](concepts/two-image-schema-fork.md) | llama-stack-platform, guardrails-and-safety, rag-and-vector-store, deployment-and-ops | 2026-05-09 |
| [wrapping-upstream-where-broken](concepts/wrapping-upstream-where-broken.md) | streamlit-playground-ui, llama-stack-platform, rag-and-vector-store, guardrails-and-safety, deployment-and-ops | 2026-05-09 |
| [helm-upgrade-staleness](concepts/helm-upgrade-staleness.md) | llama-stack-platform, models-and-inference, deployment-and-ops | 2026-05-09 |

## Recent Changes

- **2026-05-09:** Initial compilation. 8 topics, 3 concepts auto-discovered from 16 source files in `wiki/` + `wiki/handbooks/`. Schema generated from scratch (see [schema.md](schema.md)).

## Source map

Source files contributed to topics as follows. Many files contribute to multiple topics — that is intentional (the source wiki is loosely categorized; the compiled wiki re-clusters by reader intent).

| Source | Topics |
|---|---|
| [`../wiki/architecture.md`](../wiki/architecture.md) | llama-stack-platform, guardrails-and-safety, streamlit-playground-ui, rag-and-vector-store |
| [`../wiki/components.md`](../wiki/components.md) | llama-stack-platform, guardrails-and-safety, streamlit-playground-ui, models-and-inference, rag-and-vector-store, deployment-and-ops |
| [`../wiki/decisions.md`](../wiki/decisions.md) | llama-stack-platform, streamlit-playground-ui, models-and-inference, rag-and-vector-store |
| [`../wiki/entanglements.md`](../wiki/entanglements.md) | streamlit-playground-ui |
| [`../wiki/findings.md`](../wiki/findings.md) | llama-stack-platform, guardrails-and-safety, deployment-and-ops, future-work-roadmap |
| [`../wiki/future-work.md`](../wiki/future-work.md) | future-work-roadmap |
| [`../wiki/guardrails-redteam-report.md`](../wiki/guardrails-redteam-report.md) | guardrails-and-safety |
| [`../wiki/handbooks/flet-handbook.md`](../wiki/handbooks/flet-handbook.md) | flet-framework |
| [`../wiki/handbooks/llamastack-handbook.md`](../wiki/handbooks/llamastack-handbook.md) | llama-stack-platform |
| [`../wiki/llama-stack-api-improvements.md`](../wiki/llama-stack-api-improvements.md) | llama-stack-platform, streamlit-playground-ui |
| [`../wiki/model-benchmarks.md`](../wiki/model-benchmarks.md) | models-and-inference |
| [`../wiki/pitfalls.md`](../wiki/pitfalls.md) | llama-stack-platform, guardrails-and-safety, streamlit-playground-ui, models-and-inference, rag-and-vector-store, deployment-and-ops |
| [`../wiki/runbook.md`](../wiki/runbook.md) | llama-stack-platform, guardrails-and-safety, models-and-inference, rag-and-vector-store, deployment-and-ops |

## Excluded

Per [`.wiki-compiler.json`](../.wiki-compiler.json) `sources[].exclude`:
- `wiki/log.md` — wiki-maintenance changelog (recursive — describes the source wiki, not topics)
- `wiki-compiled/` — this directory itself
- `.compile-state.json`, `compile-log.md` — internal state
