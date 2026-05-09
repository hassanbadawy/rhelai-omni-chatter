# Architecture

The deployed stack is layered. Each layer has one job and is connected by stable HTTP boundaries.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  UI layer                                                                │
│   ├─ helm/llama-stack-ui (our Streamlit app, source in llama-stack-ui/) │
│   └─ helm/llama-stack-playground (genaiops upstream, optional)          │
└────────────────┬─────────────────────────────────────────────────────────┘
                 │ HTTPS (OpenShift Route, edge TLS)
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Llama Stack (helm/llama-stack)                                          │
│   - REST API on :8321  (/v1/responses, /v1/safety/run-shield, ...)      │
│   - Two image variants depending on guardrails.enabled:                  │
│       false → rh-dev (RHOAI default), inline::llama-guard               │
│       true  → llama-stack-vllm-milvus-fms, remote::trusty_fms           │
└────┬───────────────────┬───────────────────────────┬─────────────────────┘
     │                   │                           │
     │ HTTPS :8443       │ HTTP :8080                │ HTTP :19530
     ▼                   ▼                           ▼
┌─────────────┐    ┌──────────────────────┐    ┌────────────┐
│ vLLM        │    │ Guardrails           │    │ Milvus     │
│ (KServe ISv)│    │ Orchestrator        │    │ (standalone│
│ Qwen2.5-7B  │    │ + bundled detectors  │    │  or inline)│
│ gpt-oss-20b │    │ (HAP, prompt-inj,    │    │            │
│ ...         │    │  language, regex)    │    │            │
└─────────────┘    └──────────────────────┘    └────────────┘
```

## Two completely independent paths

The most important architectural fact: **inference and safety are independent paths.** The guardrails orchestrator does NOT call vLLM, and vLLM does NOT call guardrails.

```
Path 1 — LLM Inference:
  Client → Llama Stack (/v1/responses) → remote::vllm provider → vLLM → LLM model

Path 2 — Safety Checks:
  Client → Llama Stack (/v1/safety/run-shield) → remote::trusty_fms → orchestrator → detectors
```

The UI orchestrates both: it calls `/v1/safety/run-shield` on input, then `/v1/responses` for inference, then `/v1/safety/run-shield` on output. Llama Stack itself does not chain them automatically.

## Why these specific layers

### Why a custom UI (`helm/llama-stack-ui`) on top of the upstream playground

The upstream `genaiops/llama-stack-playground:0.3.0-fix` image has two blocking bugs:

- File upload crashes (`AttributeError: 'dict' object has no attribute 'content'` in `upload.py:59` — SDK 0.3.0 returns `RAGDocument` as a dict but the code uses attribute access).
- Default chat mode is **Direct**, which bypasses safety shields entirely. Shields only apply in Agent-based mode.

Our custom UI fixes both, plus adds context-length probing, SSE error detection, and shield checks on every message regardless of mode. See [`decisions.md`](decisions.md) for the full rationale.

### Why a custom Llama Stack image when guardrails are on

Upstream Llama Stack ships these safety providers: `inline::llama-guard`, `inline::prompt-guard`, `inline::code-scanner`, `remote::passthrough`, `remote::bedrock`, `remote::nvidia`. **None of them speak the IBM/FMS Guardrails Orchestrator API** (`/api/v1/text/contents`).

`remote::passthrough` was the closest candidate, but it calls `/moderations` (OpenAI format) — completely incompatible with FMS. The only solution is the custom image `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3`, which adds a `remote::trusty_fms` provider that speaks the FMS API natively.

This is why `helm/llama-stack` has two configuration modes selected by `guardrails.enabled`. They use different images, different provider types, and different config schemas (see [`pitfalls.md`](pitfalls.md) "Llama Stack Config Format — TWO DIFFERENT SCHEMAS").

### Why the guardrails orchestrator is a bundle (chart v0.2.0+)

Earlier versions of the guardrails-orchestrator chart referenced detectors deployed in a separate namespace (`ai501`). This made the chart non-self-contained — installing it on a fresh cluster required pre-existing detector InferenceServices that weren't part of the chart.

Chart v0.2.0+ inlines the detectors as plain `Deployment`+`Service` objects in the same namespace as the orchestrator, with an `initContainer` that downloads the HuggingFace model into an `emptyDir`. This makes the chart drop-in installable from the OpenShift web console (the user's stated requirement — see auto-memory `user_openshift_webconsole.md`).

### Why Milvus has two modes

`milvus.mode=inline` runs an embedded SQLite-backed Milvus inside the llama-stack pod. Lightweight, but loses all data on pod restart (no PVC behind the SQLite file).

`milvus.mode=remote` connects to a standalone Milvus service. Survives restarts, supports proper scale-out. Required for any RAG data that must persist.

The genaiops upstream chart has a [namespace-based bug](pitfalls.md#genaiops-chart-namespace-bug-remote-milvus) that gates `remote::milvus` on the namespace name containing "test" or "prod". Our chart replaced this with a simple `milvus.mode` value, so it works in any namespace.

## Data flows

### Chat with RAG and shields

```
User input
  ├─► [shield: input_shields] /v1/safety/run-shield
  │     └─► trusty_fms → orchestrator → {hap, prompt_injection, language, regex}
  ├─► [RAG] /v1/vector-stores/{id}/search → prepend chunks to prompt
  ├─► /v1/responses (streaming, previous_response_id for history)
  │     └─► remote::vllm → vLLM /v1/chat/completions
  └─► [shield: output_shields] /v1/safety/run-shield (same path as input)
```

### Document upload

```
File upload → /v1/openai/v1/files (Streamlit uses ChatCompletions-compatible files API)
  → /v1/vector-stores/{id}/files (chunk: 512 tokens, overlap: 50)
  → embeddings (inline::sentence-transformers, e.g. granite-embedding-125m)
  → Milvus
```

## What's deliberately not here

- **No agent layer.** The UI uses the Responses API directly; we deliberately do not run the upstream playground's "Agent-based" mode. See [`decisions.md`](decisions.md) "Chat Completions vs Responses API".
- **No Llama Stack middleware in the agentic-ivr PoC.** A different project (`agentic-ivr`) talks to vLLM directly via the OpenAI client. That decision is recorded there, not here.
- **No GitOps yet.** Helm charts are installed manually from the OpenShift web console. ArgoCD bootstrap is in [`future-work.md`](future-work.md).
- **No llm-d distributed inference yet.** Single-pod vLLM with KServe. See [`future-work.md`](future-work.md).

## Cross-refs

- Per-component details (chart values, image tags, model IDs): [`components.md`](components.md)
- Operational recipes (deploy, debug, register a model): [`runbook.md`](runbook.md)
- Why specific decisions were made: [`decisions.md`](decisions.md)
- Bugs hit and their root causes: [`pitfalls.md`](pitfalls.md)
- Empirical measurements (latency, throughput): [`model-benchmarks.md`](model-benchmarks.md), [`findings.md`](findings.md)
