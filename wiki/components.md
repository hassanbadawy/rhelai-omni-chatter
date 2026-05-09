# Components

Per-component rationale, current cluster URLs, model choices, image tags, and license notes. Update this when a chart version bumps, a model swap happens, or a service URL changes.

## Helm charts

All charts live under `helm/` and are published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`.

### `helm/llama-stack`

The Llama Stack chart. Two modes via `guardrails.enabled`.

| | guardrails.enabled=false | guardrails.enabled=true |
|--|--------------------------|-------------------------|
| Image | `rh-dev` (RHOAI operator default) | `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` |
| Safety provider | `inline::llama-guard` | `remote::trusty_fms` |
| Config schema | `metadata_store` + `storage.{backends,stores}` | `type: sqlite, db_path: ...` |
| Shields | empty | hap, prompt_injection, language_detection, regex |
| `external_providers_dir` | not set | `/opt/app-root/src/.llama/providers.d/` |

**Always set `vllm.modelId`** — Llama Stack auto-registers the embedding model but NOT the served LLM. Without it, `/v1/models` returns embeddings only and chat completions return `400 Bad Request: model field expected string`. After registration, the LLM is exposed with a `vllm/` prefix (e.g. `vllm/qwen25-7b-instruct`).

**Both config blocks need `tls_verify: false`** — OpenShift InferenceServices expose vLLM via kube-rbac-proxy on :8443 with self-signed TLS. Missing this in the guardrails-mode block causes `APIConnectionError 500` on every chat completion, even when curl from inside the pod works fine.

**Service name is `llama-stack-service`, not `llama-stack`.** The chart deploys a `LlamaStackDistribution` CR; the operator creates the Service. Anything connecting from inside the cluster must use `http://llama-stack-service:8321`.

### `helm/llama-stack-playground`

Standalone deploy of the upstream genaiops Streamlit playground (`quay.io/rhoai-genaiops/llama-stack-playground:0.3.0-fix`).

**Use this only when document upload and per-message shields are not needed.** The upstream image has two known bugs (see [`architecture.md`](architecture.md) "Why a custom UI"). Our `helm/llama-stack-ui` is the preferred path.

`networkPolicy.enabled` defaults to `false`. An earlier version defaulted to `true` with egress targeting label `app.kubernetes.io/name: llama-stack`, which silently blocked all outbound traffic because the llama-stack chart labels pods as `app: llama-stack`.

### `helm/llama-stack-ui`

Our custom Streamlit UI (source: `llama-stack-ui/`).

| Value | Default | Purpose |
|-------|---------|---------|
| `ui.llamaStackUrl` | `http://llama-stack-service:8321` | Backend Llama Stack URL |
| `ui.defaultModel` | `""` | Pre-selected model (must include `vllm/` prefix) |
| `image.repository` | `image-registry.openshift-image-registry.svc:5000/<ns>/llama-stack-ui` | In-cluster image |
| `route.enabled` | `true` | OpenShift Route, edge TLS |

The chart sets `LLAMA_STACK_UI_DATA_DIR=/tmp/llama-stack-ui-data` so the read-only baked `config.yaml` (in the image) is bypassed and helm-managed env vars (`LLAMA_STACK_API_ENDPOINT`, `DEFAULT_MODEL`) take effect. Settings page changes persist in `/tmp/llama-stack-ui-data/config.yaml` until pod restart. See [`runbook.md`](runbook.md) for the build process.

### `helm/guardrails-orchestrator`

Self-contained as of v0.2.0. Bundles the orchestrator and all detectors as `Deployment`+`Service` pairs.

| Detector key | HuggingFace model | initContainer memory |
|---|---|---|
| `hap` | `ibm-granite/granite-guardian-hap-125m` | 2Gi |
| `prompt_injection` | `protectai/deberta-v3-base-prompt-injection-v2` | 2Gi |
| `language_detection` | `papluca/xlm-roberta-base-language-detection` | 4Gi |
| `regex_competitor` | (built-in to orchestrator, no model) | — |

Each `type: huggingface` detector entry auto-generates the deployment via `snapshot_download()` into an `emptyDir` at `/mnt/models`, with `MODEL_DIR=/mnt/models` in the main container.

**`chunker.hostname` must be empty or a real service.** Setting it to anything else (e.g. a namespace name) fails with `missing field 'service'`. Default is loopback `127.0.0.1:8085` when empty.

**`confidence_threshold` must be set explicitly.** A blank threshold renders as YAML null and causes `'>' not supported between 'float' and 'NoneType'`. Defaults: `hap=0.5, prompt_injection=0.5, language_detection=0.85, regex=0.5`.

For gated HF models, set `detectorDefaults.hfToken` (global) or `hfToken` per-detector. Stored in a `guardrails-hf-token` Secret.

### `helm/milvus`

Standalone Milvus, optional. Default token `root:Milvus`. Required token field on `remote::milvus` provider; missing it fails with `Field required`.

### Other charts (supporting services)

`anythingllm`, `dashy`, `docling-serve`, `gitea`, `langflow`, `litemaas`, `minio`, `n8n`, `pgadmin`, `postgresql`, `postgresql-stack`, `postgrest`, `qdrant`, `swagger-ui` — see each chart's `README` and `values.yaml`. None are part of the core inference path; they are utilities for the broader RHOAI environment.

## Models

Registered via Llama Stack `vllm.modelId` and exposed with `vllm/` prefix.

| Model ID | Use case | Notes |
|----------|----------|-------|
| `vllm/qwen25-7b-instruct` | Voice agent, plain chat, multilingual (ar/ur/hi/id) | TTFT to user-visible content ~45 ms. ForCausalLM, no thinking trace. |
| `vllm/gpt-oss-20b` | Long RAG answers, agent/tool flows | ~98 tok/s throughput vs ~30 for qwen25. TTFT ~500 ms (silent reasoning trace). |
| `vllm/qwen3-*` | Avoid for streaming UI | Emits `<think>...</think>` reasoning trace that eats `max_tokens` budget. Mitigations: vLLM `--reasoning-parser qwen3`, UI strip, or use qwen25-7b. |
| `vllm/gemma-3n-e4b` | DO NOT USE on RHOAI vLLM | `Gemma3nForConditionalGeneration` (multimodal hybrid) text decoder is broken on `0.13.0+rhai11` and `0.11.2+rhai5` — `completion_tokens > 0` but `content: ""`. Stay on `ForCausalLM`. |

Reasoning-model UIs must surface `delta.reasoning_content` (and legacy `delta.reasoning`) — a UI that only reads `delta.content` looks frozen until the model finishes reasoning.

Embedding model (auto-registered by `inline::sentence-transformers`):
- `granite-embedding-125m` — 768-dim. Set `embedding_dimension: 768` on vector store creation; empty string causes `400 Bad Request`.

## Shields

Wired to `remote::trusty_fms` only when `guardrails.enabled=true`. See [`guardrails-redteam-report.md`](guardrails-redteam-report.md) for adversarial test results.

| Shield ID | Detector | Catches | Caveats |
|-----------|----------|---------|---------|
| `hap` | guardrails-detector-ibm-hap | Hate, abuse, profanity | — |
| `prompt_injection` | prompt-injection-detector | Prompt injection attacks | — |
| `language_detection` | language-detector | Non-English text | Mis-classifies short greetings (`hi`, `hey`) as non-English at >0.9 confidence. Drop the shield, raise threshold to ≥0.99, or skip on short messages. |
| `regex` | Built-in (no model) | Custom patterns (PII, profanity, brand mentions) | Configure in `guardrails.regex.filter` array. |

## Cluster URLs (current — verify before quoting)

OpenShift cluster credentials in `.env`. Internal URLs are accessible only from inside the cluster.

| Component | Internal URL |
|-----------|--------------|
| Llama Stack | `http://llama-stack-service:8321` |
| HAP detector | `http://guardrails-detector-ibm-hap-predictor.ai501.svc:8000` |
| Prompt-injection detector | `http://prompt-injection-detector-predictor.ai501.svc:8000` |
| Language detector | `http://language-detector-predictor.ai501.svc:8000` |
| Milvus (when remote) | `http://milvus.<ns>.svc:19530` |

`ai501` is the legacy shared-detectors namespace. New deployments via `helm/guardrails-orchestrator` v0.2.0+ run detectors in the same namespace as the orchestrator and don't need `ai501`.

## Helm repo

Published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`. Chart packages stored as GitHub Releases; `index.yaml` on `gh-pages` branch.

```bash
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install llama-stack hassanbadawy/llama-stack
```

Release flow: bump `Chart.yaml` version → `helm package` → `gh release create` → update `gh-pages` `index.yaml` via `helm repo index --merge`.
