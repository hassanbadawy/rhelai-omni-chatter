# Wiki schema — rhelai-omni-chatter

This file is the source of truth for wiki structure: topic slugs, concept slugs, and naming conventions. The compiler reads this before classifying sources. You can edit this file between compiles to rename topics, merge them, or change conventions — the compiler will respect those changes on next run.

## Topics

| Slug | Description | Aliases |
|---|---|---|
| `llama-stack-platform` | Llama Stack as the orchestration layer — two image variants (rh-dev vs FMS), config schemas, providers, REST API surface (Chat Completions, vector_io, safety), operational concerns. | llama-stack, llamastack, orchestration |
| `guardrails-and-safety` | The safety/guardrails layer — IBM/FMS detectors (HAP, prompt_injection, language_detection, regex), the `remote::trusty_fms` provider, orchestrator self-contained chart, red-team test results. | guardrails, shields, trusty_fms, hap, prompt-injection, fms |
| `streamlit-playground-ui` | The Streamlit playground UI in `llama-stack-ui/` and its helm chart — pages, session state, config flow, and why we built our own instead of using upstream genaiops. | ui, streamlit, playground, llama-stack-ui |
| `models-and-inference` | LLMs and embedding models in this stack — Qwen2.5-7B, gpt-oss-20b, Qwen3 (avoid for streaming), Gemma 3n (broken), granite-embedding-125m. Latency, throughput, use-case routing. | vllm, models, qwen, gpt-oss, gemma, embeddings, inference |
| `rag-and-vector-store` | RAG path — file upload → chunk → embed → Milvus → search. Two Milvus modes (inline embedded vs remote standalone), provider gotchas, route timeout. | rag, milvus, vector-store, embeddings, retrieval |
| `deployment-and-ops` | Helm-based deployment on OpenShift — chart catalog, gh-pages helm repo, deploy/upgrade recipes, debugging procedures. | helm, deploy, ops, openshift, runbook |
| `flet-framework` | Flet primer for the future student-assistant app — Python framework for cross-platform desktop/web/mobile, Page model, navigation, packaging, services architecture. | flet, ui-framework, mobile, cross-platform |
| `future-work-roadmap` | Forward-looking ideas not yet implemented — GitOps via ArgoCD, fresh-cluster bootstrap, llm-d distributed inference, the staged Karpathy-llm-wiki tooling roadmap. | future, roadmap, argocd, llm-d, gitops, wiki-tooling |

## Concepts

| Slug | Description | Connects |
|---|---|---|
| `two-image-schema-fork` | The rh-dev vs llama-stack-vllm-milvus-fms image fork drives different config schemas, and the cascade goes deeper than a feature toggle. | llama-stack-platform, guardrails-and-safety, rag-and-vector-store, deployment-and-ops |
| `wrapping-upstream-where-broken` | Recurring response pattern: where upstream blocks deployment in the OpenShift web console, we wrap it in a chart we control. Custom UI, custom Llama Stack image, fixed Milvus mode flag, self-contained orchestrator. | streamlit-playground-ui, llama-stack-platform, rag-and-vector-store, guardrails-and-safety, deployment-and-ops |
| `helm-upgrade-staleness` | `helm upgrade --reuse-values` carries forward `vllm.url`/`vllm.apiToken`/`vllm.modelId` from the previous install, going stale when the underlying InferenceService rotates SA tokens or gets renamed. The fix is operational discipline, not a chart change. | llama-stack-platform, models-and-inference, deployment-and-ops |

## Topic-slug conventions

- Lowercase-kebab-case
- Descriptive but short (2–4 hyphens)
- Match the user's mental model, not the directory layout (the source `wiki/` is loosely organized; the compiled wiki re-clusters by reader intent)
- Avoid "and" where a single word works — but compound nouns (`rag-and-vector-store`, `deployment-and-ops`) are OK when the topic genuinely spans two equally-weighted domains

## Concept-slug conventions

- Lowercase-kebab-case
- Phrase as a noun (the pattern itself), not as a verb
- Length up to 5 hyphens — concepts often need more words to convey the synthesis

## Evolution log

- **2026-05-09:** Initial schema generated from 8 topics, 3 concepts. Source corpus: 14 markdown files in `wiki/` + 2 handbooks in `wiki/handbooks/` (16 files total, `log.md` excluded by config). All topics and concepts auto-discovered on first compile run.
