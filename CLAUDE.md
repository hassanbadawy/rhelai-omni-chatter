# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**rhelai-omni-chatter** — a multi-service AI platform deployed on Red Hat OpenShift. The core components are:

1. **Llama Stack** — LLM inference server with RAG, safety shields, agents, and the Responses API
2. **Llama Stack Playground** (`llama-stack-ui/`) — Streamlit UI for chat, documents/RAG, and settings
3. **Guardrails Orchestrator** — Server-side content safety (HAP, prompt injection, language detection, regex)
4. **Milvus** — Vector database for RAG (standalone or inline)
5. **Helm Charts** (`helm/`) — Deployable charts for all components, published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`

Supporting services: Langflow, n8n, PostgreSQL, PostgREST, Swagger UI, Dashy, MinIO.

## Local wiki discipline (Karpathy LLM-wiki pattern)

Reference: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

**The wiki at [`wiki/`](wiki/) is the persistent memory of this project.** It is append-mostly, cross-referenced markdown that accumulates findings across sessions. Treat it as the source of truth, not a side artefact.

### Read order — always wiki first

Before answering any question or writing any code, follow this order:

1. **[`wiki/README.md`](wiki/README.md)** → orient. Catalog of every wiki page with one-line hooks.
2. **[`wiki/architecture.md`](wiki/architecture.md)** → layered design (UI → Llama Stack → vLLM/Guardrails/Milvus); the two independent paths (inference vs safety).
3. **[`wiki/components.md`](wiki/components.md)** → per-component rationale, current cluster URLs, model choices, helm chart status, license notes.
4. **[`wiki/findings.md`](wiki/findings.md)** → empirical results, dated, in chronological order. Many "obvious" answers are already here with a date and a why.
5. **[`wiki/runbook.md`](wiki/runbook.md)** → operational recipes (deploy guardrails, register a model, debug TLS, file a release).
6. **[`wiki/decisions.md`](wiki/decisions.md)** → architectural decisions with rationale (Chat Completions vs Responses API, client-side history, context probing).
7. **[`wiki/pitfalls.md`](wiki/pitfalls.md)** → pitfall log with root cause and fix for every non-obvious bug hit so far.
8. **[`wiki/log.md`](wiki/log.md)** → append-only chronological record of every wiki operation.
9. Topic pages: [`wiki/entanglements.md`](wiki/entanglements.md), [`wiki/llama-stack-api-improvements.md`](wiki/llama-stack-api-improvements.md), [`wiki/model-benchmarks.md`](wiki/model-benchmarks.md), [`wiki/guardrails-redteam-report.md`](wiki/guardrails-redteam-report.md), [`wiki/future-work.md`](wiki/future-work.md).
10. Reference handbooks: [`wiki/handbooks/llamastack-handbook.md`](wiki/handbooks/llamastack-handbook.md), [`wiki/handbooks/flet-handbook.md`](wiki/handbooks/flet-handbook.md).

Only fall back to reading raw source (helm values, manifests, Streamlit code) if the wiki does not have the answer. The wiki is compiled, dated, and consistent; raw files may have stale comments.

### Write order — every non-trivial finding must be persisted

When you discover, decide, fix, or measure anything that a future Claude session would need to know, you **must** update the wiki before considering the task done. The pattern:

1. **Pick the right page.** Empirical result with a date → `findings.md`. New runtime / model component or rationale change → `components.md`. New operational recipe → `runbook.md`. Architectural decision → `decisions.md`. New bug with a root cause and fix → `pitfalls.md`. New topic that doesn't fit → create a new page under `wiki/`.
2. **Update the page in place** — keep dated entries, do not silently rewrite history. New entries go at the top (or in the chronological position called for by the page convention).
3. **Append an entry to [`wiki/log.md`](wiki/log.md)** describing what was ingested, which pages were updated, the source, and the key facts. Use the existing log format (date header, **Operation**, **Pages updated**, **Source**, **Cross-refs**, **claude-mem** ID if applicable). The log is append-only; never edit prior entries.
4. **Cross-link.** If the new content references another page, link to it (`pitfalls.md` ↔ `decisions.md` ↔ `components.md` etc.). The graph matters as much as the nodes.

### Karpathy-style rules to follow

- **Persist, do not answer in place.** When a session uncovers a fact, the right move is to write it into the wiki first, then answer the user from the wiki. The wiki is what survives compaction; the chat does not.
- **Date everything.** Every finding gets the day it was observed. Stale claims are obvious only if they're dated.
- **One page per topic, additively edited.** Don't create `findings_v2.md`. Don't fork a page when you can append a dated entry.
- **Quote the source.** Cluster URL, file path, error message verbatim, command output, exact YAML stanza. Future Claude needs the exact string to grep for.
- **Record failure as well as success.** "We tried X and it failed because Y" is among the highest-value content. The Gemma 3n empty-output finding and the `remote::passthrough`-vs-IBM-detectors mismatch are canonical examples — they prevent the same dead end being walked again.
- **Cross-link aggressively.** A finding without a link to the related component or runbook entry is half-finished.
- **No silent rewrites.** If a prior wiki entry turns out to be wrong, *append a correction with a date* and link to the prior entry; do not edit the prior entry to make it look right.
- **The log is the audit trail.** Anyone reading [`wiki/log.md`](wiki/log.md) top-to-bottom should be able to reconstruct the project's evolution.

### Sources and lint

- Raw research artefacts (web fetches, vendor docs, transcripts) live in [`wiki/sources/`](wiki/sources/) with required frontmatter (`fetched`, `url`, `fetcher`, `sha256`). See [`wiki/SOURCES.md`](wiki/SOURCES.md) for the contract. Sources are immutable — corrections go in sibling `*.notes.md` files.
- Run `python3 scripts/wiki_lint.py` to check for broken internal links, orphan pages, missing source frontmatter, and `log.md` date monotonicity. Run before every commit that touches `wiki/`.

## Repository Structure

```
├── helm/
│   ├── llama-stack/              # Llama Stack chart (guardrails + milvus + RAG)
│   ├── llama-stack-playground/   # Streamlit playground UI chart (standalone, points at any Llama Stack)
│   ├── llama-stack-ui/           # Our custom Streamlit UI chart (built from llama-stack-ui/)
│   ├── guardrails-orchestrator/  # Orchestrator + bundled HF detectors (v0.2.0+, self-contained)
│   ├── anythingllm/
│   ├── dashy/
│   ├── docling-serve/
│   ├── gitea/
│   ├── langflow/
│   ├── litemaas/
│   ├── milvus/
│   ├── minio/
│   ├── n8n/
│   ├── pgadmin/
│   ├── postgresql/
│   ├── postgresql-stack/
│   ├── postgrest/
│   ├── qdrant/
│   └── swagger-ui/
├── llama-stack-ui/           # Streamlit playground app
│   ├── app.py                # Entry point
│   ├── pages/
│   │   ├── chat.py           # Chat with streaming, RAG, and safety shields
│   │   ├── documents.py      # Vector store management, file upload
│   │   └── settings.py       # Endpoint, model, shields, and sampling config
│   ├── modules/
│   │   ├── api.py            # LlamaStackClient — all REST API calls
│   │   └── config.py         # YAML config loader/saver
│   ├── tests/
│   │   ├── test-env.sh       # Configurable endpoints for tests
│   │   └── test-guardrails.sh # 18 e2e guardrails test scenarios
│   └── config.yaml           # Runtime config (endpoint, model, shields, etc.)
├── wiki/                     # Living wiki — READ BEFORE ANSWERING (Karpathy llm-wiki pattern)
│   ├── README.md             # Index — orient here first
│   ├── architecture.md       # Layered design, two independent paths
│   ├── components.md         # Per-component rationale, URLs, models
│   ├── findings.md           # Dated empirical results
│   ├── runbook.md            # Operational recipes
│   ├── decisions.md          # Architectural decisions with rationale
│   ├── pitfalls.md           # Bug log with root causes and fixes
│   ├── entanglements.md      # Cross-file dependencies and dead code
│   ├── llama-stack-api-improvements.md  # Future improvement ideas
│   ├── model-benchmarks.md   # Latency/throughput per model + use-case routing
│   ├── guardrails-redteam-report.md  # Red-team results across the four shields
│   ├── future-work.md        # Ideas explored but not implemented
│   ├── log.md                # Append-only changelog of wiki operations
│   ├── SOURCES.md            # Frontmatter contract for sources/
│   ├── sources/              # Immutable raw research artefacts
│   ├── entities/             # Single-concept pages (empty until needed)
│   └── handbooks/            # Zero-to-hero reference handbooks
│       ├── flet-handbook.md
│       └── llamastack-handbook.md
├── scripts/
│   └── wiki_lint.py          # Mechanical wiki integrity checks
├── .env                      # OpenShift cluster credentials (NEVER commit secrets)
└── tests/
    └── test-llamastack.sh    # Llama Stack API tests
```

## Helm Chart: llama-stack (`helm/llama-stack/`)

### Two Modes

The chart operates in two modes controlled by `guardrails.enabled`:

| | Default Mode | Guardrails Mode |
|--|-------------|----------------|
| Image | `rh-dev` (RHOAI operator default) | `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` |
| Safety provider | `inline::llama-guard` | `remote::trusty_fms` → guardrails-orchestrator |
| Config format | `backend`/`namespace` style kvstores | `type: sqlite` with `db_path` |
| Shields | Empty | hap, prompt_injection, language_detection, regex |
| Extra fields | `metadata_store`, `storage` blocks | `external_providers_dir` |

### Deploy with Guardrails

```bash
helm upgrade llama-stack helm/llama-stack/ -n <namespace> \
  --set guardrails.enabled=true \
  --set guardrails.hap.enabled=true \
  --set guardrails.prompt_injection.enabled=true \
  --set guardrails.language_detection.enabled=true \
  --set guardrails.regex.enabled=true \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.<namespace>.svc:19530" \
  --set vllm.url="http://<vllm-predictor>.<namespace>.svc:8080/v1"
```

### Deploy without Guardrails

```bash
helm upgrade llama-stack helm/llama-stack/ -n <namespace> \
  --set vllm.url="http://<vllm-predictor>.<namespace>.svc:8080/v1"
```

### Milvus Modes

- `milvus.mode=inline` (default) — embedded Milvus with SQLite **inside the llama-stack pod**. No external service needed, but data is **lost on every pod restart** (no PVC backing the SQLite file).
- `milvus.mode=remote` — connects to a standalone Milvus service. Default token `root:Milvus`. Use this for any RAG data that must survive restarts.

Verify which mode is live with:
```bash
oc exec -n <ns> deployment/llama-stack -- curl -s http://llama-stack-service:8321/v1/providers \
  | jq '.[] | select(.api=="vector_io") | {provider_id, provider_type}'
```

### Required values when registering an LLM

Llama Stack auto-registers the embedding model but **not** the vLLM-served LLM. The chart needs `vllm.modelId` set to the served-model-name, and the model is exposed via `/v1/models` with a `vllm/` prefix (e.g. `vllm.modelId=qwen25-7b-instruct` → `/v1/models` returns `vllm/qwen25-7b-instruct`). UIs must use the prefixed identifier when sending chat completions.

### Operator service name

The chart deploys a `LlamaStackDistribution` CR; the **operator** then creates the Service as `llama-stack-service` (not `llama-stack`). Anything that connects to llama-stack from inside the cluster must use `http://llama-stack-service:8321`.

### Helm upgrade caveat

`--reuse-values` carries forward whatever was previously set, including `vllm.url`, `vllm.apiToken`, `vllm.modelId`. When the running InferenceService is swapped (model change) or its SA token is rotated, those reused values go stale and cause `APIConnectionError` (DNS) or `404 model not found`. Always re-source these from the live cluster on every upgrade:
```bash
TOKEN=$(oc get secret -n <ns> default-token-<isvc>-sa -o jsonpath='{.data.token}' | base64 -d)
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set vllm.url="https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="<isvc>"
```

### Helm Repo

Published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`. Chart packages are stored as GitHub Releases, `index.yaml` on `gh-pages` branch.

```bash
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install llama-stack hassanbadawy/llama-stack
```

To publish a new version: bump `Chart.yaml` version, `helm package`, `gh release create`, update `gh-pages` index.yaml via `helm repo index --merge`.

## Helm Chart: llama-stack-playground (`helm/llama-stack-playground/`)

A standalone Helm chart that deploys the Streamlit playground UI (`quay.io/rhoai-genaiops/llama-stack-playground:0.3.0-fix`) as an OpenShift workload. It is **independent** of the `llama-stack` chart — it only needs a Llama Stack backend URL to connect to.

**Known bugs in the upstream image:**
- File upload crashes with `AttributeError: 'dict' object has no attribute 'content'` at `/app/llama_stack/distribution/ui/page/upload/upload.py:59` — the SDK 0.3.0 returns `RAGDocument` as a dict but the code uses attribute access. Use `helm/llama-stack-ui` for document upload until upstream fixes this.
- Default chat mode is **Direct**, which bypasses safety shields entirely. Shields only apply in **Agent-based** mode (and even there, the agent runtime wraps the user message before calling the safety API). If you need shields on every plain chat message, use `helm/llama-stack-ui` instead.

### Key values

| Value | Default | Purpose |
|-------|---------|---------|
| `playground.llamaStackUrl` | `http://llama-stack:8321` | Llama Stack backend URL — override to point at your llama-stack service |
| `playground.defaultModel` | `meta-llama/Llama-3.2-3B-Instruct` | Default model pre-selected in the UI |
| `image.repository` | `quay.io/rhoai-genaiops/llama-stack-playground` | Container image |
| `image.tag` | `0.3.0-fix` | Image tag |
| `route.enabled` | `true` | Creates an OpenShift Route with TLS edge termination |

### Quick deploy

```bash
# Deploy alongside the llama-stack chart in the same namespace (uses in-cluster service name)
helm install llama-stack-playground helm/llama-stack-playground/ -n <namespace>

# Point at an external or different namespace llama-stack
helm install llama-stack-playground helm/llama-stack-playground/ -n <namespace> \
  --set playground.llamaStackUrl="http://llama-stack.<other-ns>.svc:8321"
```

### NetworkPolicy

`networkPolicy.enabled` defaults to `false`. An earlier version defaulted to `true` with egress targeting label `app.kubernetes.io/name: llama-stack`, which caused `APIConnectionError` because the llama-stack chart labels pods as `app: llama-stack` — a mismatch that silently blocked all outbound traffic from the playground.

## Helm Chart: llama-stack-ui (`helm/llama-stack-ui/`)

A standalone Helm chart that deploys our **custom** Streamlit UI (`llama-stack-ui/` source dir) as an OpenShift workload. Use this in preference to the genaiops `llama-stack-playground` chart when you need:

- Working document upload (genaiops 0.3.0-fix has a `RAGDocument` dict-vs-object bug that breaks file uploads)
- Context-length probing (`max_tokens` capped to `context_length / 2` for small-context models)
- SSE error detection in HTTP 200 streams
- Conversation history with safety-shield checks on input AND output

### Building the image

The chart defaults to the OpenShift internal registry. Build from source first:

```bash
oc new-build --binary --strategy=docker --name=llama-stack-ui -n <namespace>
oc patch bc/llama-stack-ui -n <namespace> --type=json \
  -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]'
oc start-build llama-stack-ui --from-dir=./llama-stack-ui --follow -n <namespace>
```

Or override `image.repository` to point at a public image you've built and pushed yourself.

### Key values

| Value | Default | Purpose |
|-------|---------|---------|
| `ui.llamaStackUrl` | `http://llama-stack-service:8321` | Llama Stack backend URL — exported as `LLAMA_STACK_API_ENDPOINT` |
| `ui.defaultModel` | `""` | Default model — exported as `DEFAULT_MODEL`. Must include the `vllm/` prefix (e.g. `vllm/qwen25-7b-instruct`) |
| `image.repository` | `image-registry.openshift-image-registry.svc:5000/<namespace>/llama-stack-ui` | In-cluster image — `<namespace>` is whichever namespace ran `oc new-build`. Override for external registries. |
| `route.enabled` | `true` | Creates an OpenShift Route with TLS edge termination |

### Config sourcing

The UI loads its config from `config.yaml` first, then falls back to env vars (`LLAMA_STACK_API_ENDPOINT`, `DEFAULT_MODEL`). To make the helm-managed env vars actually apply, the chart sets `LLAMA_STACK_UI_DATA_DIR=/tmp/llama-stack-ui-data` so the read-only baked `config.yaml` (in the image) is bypassed and the env-var defaults take effect on first launch. Users can then override values from the Settings page; changes persist in `/tmp/llama-stack-ui-data/config.yaml` until the pod restarts.

### Quick deploy

```bash
helm install llama-stack-ui helm/llama-stack-ui/ -n <namespace> \
  --set ui.llamaStackUrl="http://llama-stack-service:8321" \
  --set ui.defaultModel="vllm/qwen25-7b-instruct"
```

## Streamlit Playground (`llama-stack-ui/`)

### Architecture

- **`app.py`** — Entry point, Streamlit page navigation
- **`pages/chat.py`** — Chat with streaming via Responses API (`/v1/responses`), optional RAG from vector stores, server-side safety shields via `/v1/safety/run-shield`
- **`pages/documents.py`** — Vector store CRUD, file upload with chunking (512 tokens, 50 overlap), search
- **`pages/settings.py`** — Endpoint, model selection (from `/v1/models`), embedding model, safety shields (multiselect from `/v1/shields`), sampling parameters, language, system prompt
- **`modules/api.py`** — `LlamaStackClient` class wrapping all Llama Stack REST endpoints
- **`modules/config.py`** — YAML config with defaults, persists to `config.yaml`

### Data Flow

```
User input → [input shields check via /v1/safety/run-shield]
           → [RAG: search vector store → prepend chunks to prompt]
           → /v1/responses (streaming, with previous_response_id for history)
           → [output shields check via /v1/safety/run-shield]
           → Display response
```

### Safety Shields in the UI

Shields are **fully server-side** — the UI calls Llama Stack's `/v1/safety/run-shield` which delegates to `remote::trusty_fms` → guardrails-orchestrator → detectors. No external guardrails endpoints are exposed to the UI.

Settings page shows shields from `/v1/shields` as multiselect checkboxes for input and output. Config stores `input_shields` and `output_shields` as lists of shield IDs.

### Running Locally

```bash
cd llama-stack-ui
export LLAMA_STACK_API_ENDPOINT="https://llama-stack-<namespace>.apps.<cluster>"
streamlit run app.py
# or: ./run.sh
```

### Config Keys (`config.yaml`)

| Key | Type | Purpose |
|-----|------|---------|
| `endpoint` | string | Llama Stack API URL |
| `model` | string | LLM model ID (e.g. `vllm/llama32`) |
| `embedding_model` | string | Embedding model ID (e.g. `granite-embedding-125m`) |
| `embedding_dimension` | int | Embedding vector dimension (e.g. `768`) |
| `vector_io_provider` | string | Vector store provider (e.g. `milvus`) |
| `safety_enabled` | bool | Enable/disable shield checks |
| `input_shields` | list | Shield IDs to run on user input |
| `output_shields` | list | Shield IDs to run on LLM output |
| `temperature` | float | Sampling temperature |
| `top_p` | float | Top-p sampling |
| `max_tokens` | int | Max output tokens |
| `language` | string | UI language |
| `system_prompt` | string | System prompt for chat |
| `user_id` | string | User identifier for conversation history |

## Guardrails Architecture

### Upstream Llama Stack Safety Providers (What Exists Natively)

Llama Stack has **no built-in regex provider** and **no native IBM detector support**:

| Provider | Type | Needs Model? | Compatible with IBM detectors? |
|----------|------|-------------|-------------------------------|
| `inline::llama-guard` | Content moderation | Yes (Llama Guard model on vLLM) | No |
| `inline::prompt-guard` | Prompt injection detection | Yes (transformers model) | No |
| `inline::code-scanner` | Code vulnerability scanning | No (uses `codeshield` lib) | No |
| `remote::passthrough` | Proxy to any HTTP service | No | **No** — calls `/moderations` (OpenAI format) |
| `remote::bedrock` | AWS Bedrock safety | No (cloud API) | No |
| `remote::nvidia` | NVIDIA NIM safety | No (cloud API) | No |

### Why `remote::passthrough` Does NOT Work with IBM Detectors

The APIs are completely different:

| | Llama Stack `remote::passthrough` | IBM/FMS Guardrails Detectors |
|--|----------------------------------|------------------------------|
| Endpoint | `POST /moderations` | `POST /api/v1/text/contents` |
| Request | `{"input": "text", "model": "shield_id"}` | `{"contents": ["text"], "detector_params": {"threshold": 0.5}}` |
| Response | `{"results": [{"flagged": bool}]}` | `[[{"detection_type": "...", "score": 0.99}]]` |

### The Solution: `remote::trusty_fms` (Custom Provider)

The `genaiops/llama-stack-operator-instance` chart uses a **custom image** (`quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3`) that includes a `remote::trusty_fms` provider. This provider:

1. Speaks the IBM/FMS Guardrails Orchestrator API natively
2. Routes shield checks through the orchestrator to individual detectors
3. Is NOT available in the standard `rh-dev` image — only in the custom FMS image
4. Requires `external_providers_dir: /opt/app-root/src/.llama/providers.d/` in config

Our chart was updated to use this image and provider when `guardrails.enabled=true`. When disabled, it falls back to the standard `rh-dev` image with `inline::llama-guard`.

### Two Separate Paths (Inference vs Safety)

Llama Stack has **two completely independent paths** — the guardrails orchestrator does NOT connect to vLLM:

```
Path 1 — LLM Inference:
  Client → Llama Stack → remote::vllm provider → vLLM server → LLM model

Path 2 — Safety Checks:
  Client → Llama Stack → remote::trusty_fms provider → guardrails-orchestrator → detectors
```

These paths never intersect. The orchestrator only routes text to lightweight classifier models (HAP, prompt injection, language detection) and regex — it has no knowledge of or connection to the vLLM inference server.

### Flow (Server-Side)

```
Llama Stack (/v1/safety/run-shield)
    → remote::trusty_fms provider
        → guardrails-orchestrator (port 8080, internal)
            → HAP detector (ai501 namespace, port 8000)
            → prompt-injection detector (ai501 namespace, port 8000)
            → language detector (ai501 namespace, port 8000)
            → regex detector (built-in to orchestrator)
```

### Detector API Format (IBM/FMS guardrails)

All detectors use the same API:
```
POST {url}/api/v1/text/contents
{"contents": ["text"], "detector_params": {"threshold": 0.5}}

Clean: [[]]
Violation: [[{"text":"...","detection_type":"INJECTION","score":0.99,...}]]
```

### Available Shields

| Shield ID | Detector | What It Catches |
|-----------|----------|----------------|
| `hap` | guardrails-detector-ibm-hap | Hate, abuse, profanity |
| `prompt_injection` | prompt-injection-detector | Prompt injection attacks |
| `language_detection` | language-detector | Non-English text. **Caveat:** the underlying `papluca/xlm-roberta-base-language-detection` model mis-classifies short greetings (`hi`, `hey, how are you`) as non-English at >0.9 confidence. Either drop this shield, raise its threshold to ≥0.99, or skip it for short messages. |
| `regex` | Built-in regex | Custom patterns (e.g. `(?i).*fight club.*`) |

### Regex Shield — Pattern Examples

The regex shield is configured in the helm chart's `guardrails.regex.filter` array. Common patterns:

| Name | Pattern | Use Case |
|------|---------|----------|
| Block SSNs | `\b\d{3}-\d{2}-\d{4}\b` | Filter social security numbers |
| Block Emails | `\b[\w.-]+@[\w.-]+\.\w+\b` | Filter email addresses |
| Block Phone Numbers | `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` | Filter phone numbers |
| Block Keywords | `(?i).*(fight club|competitor).*` | Block specific words/phrases |
| Profanity Filter | `\b(word1\|word2\|word3)\b` | Block profanity |

Regex patterns are checked server-side by the guardrails orchestrator (no model needed). Configure via helm:
```yaml
guardrails:
  regex:
    enabled: true
    filter:
      - "(?i).*fight club.*"
      - "\\b\\d{3}-\\d{2}-\\d{4}\\b"
```

### Testing Guardrails

```bash
cd llama-stack-ui
./tests/test-guardrails.sh    # 18 e2e tests
```

Edit `tests/test-env.sh` to point at different endpoints.

### `helm/guardrails-orchestrator` — Self-Contained Detector Deployments (v0.2.0+)

As of chart v0.2.0, detectors are **bundled in the chart** — no external namespace (`ai501`) or KServe dependency required. Each detector entry with `type: huggingface` automatically deploys a `Deployment` + `Service` in the same namespace.

#### How it works

An `initContainer` (using the same runtime image) downloads the HuggingFace model via `snapshot_download()` into an `emptyDir` volume at `/mnt/models`. The main container then loads from `MODEL_DIR=/mnt/models`.

#### Detector models

| Detector key | HuggingFace model | Memory (init) |
|---|---|---|
| `hap` | `ibm-granite/granite-guardian-hap-125m` | 2Gi |
| `prompt_injection` | `protectai/deberta-v3-base-prompt-injection-v2` | 2Gi |
| `language_detection` | `papluca/xlm-roberta-base-language-detection` | 4Gi |
| `regex_competitor` | Built-in sidecar (no model) | — |

#### Adding a new detector

Add an entry to `detectors:` in `values.yaml` — no template changes needed:

```yaml
detectors:
  my_detector:
    enabled: true
    type: huggingface
    modelId: "org/model-name"    # HuggingFace model ID
    hfToken: "hf_xxx"            # optional — only for gated/private models
    hostname: "my-detector"      # must use dashes, no underscores
    port: 8000
    threshold: 0.5
    input: true
    output: true
    params: {}
```

For gated models, set `detectorDefaults.hfToken` (global) or `hfToken` per-detector. Token is stored in a `guardrails-hf-token` Secret.

#### Critical: `chunker.hostname` must be empty or a real service

Leave `chunker.hostname: ""` unless you have a separate chunker service. Setting it to anything (e.g. a namespace name) causes the orchestrator to fail with `missing field 'service'` on startup. The chart defaults to `127.0.0.1:8085` (loopback) when hostname is empty, which satisfies the config schema even though no chunker is running.

#### Critical: `confidence_threshold` must be set explicitly

When enabling shields via `--set guardrails.hap.enabled=true`, always also set the threshold. A blank threshold renders as YAML null, causing `'>' not supported between 'float' and 'NoneType'` in the provider. Default values: `hap=0.5`, `prompt_injection=0.5`, `language_detection=0.85`, `regex=0.5`.

## Critical Knowledge — Pitfalls to Avoid

### Llama Stack Config Format (TWO DIFFERENT SCHEMAS)

The `rh-dev` image and the custom `llama-stack-vllm-milvus-fms` image use **different config schemas**:

| Field | rh-dev image | Custom (FMS) image |
|-------|-------------|-------------------|
| Storage | `metadata_store` + `storage.backends` + `storage.stores` | NOT supported — causes `ValidationError` |
| Kvstore | `backend: default, namespace: "x"` | `type: sqlite, db_path: /path/store.db` |
| Files metadata | `backend: sql, namespace: files` | `type: sqlite, db_path: /path/files.db` |
| vLLM config key | `base_url` | `url` |

**Never mix config formats between images.** The helm chart handles this with the `guardrails.enabled` conditional — two completely separate config blocks.

### Remote Milvus Requires Token

`remote::milvus` provider requires a `token` field or it fails with `Field required`. Default is `root:Milvus`. Our chart sets this automatically. The genaiops chart also handles this.

### Genaiops Chart Namespace Bug (remote::milvus)

The `genaiops/llama-stack-operator-instance` chart has a template condition that only includes `remote::milvus` when the namespace contains "test" or "prod":

```go
{{- if and .Values.rag.enabled (or (contains "test" .Release.Namespace) (contains "prod" .Release.Namespace)) }}
vector_io:
- provider_id: milvus
  provider_type: remote::milvus    # <-- only for test/prod namespaces
{{- end }}
```

For namespaces like `user1-canopy`, `user2-canopy`, or any custom name, you get `inline::milvus` even with `rag.enabled=true`. This means:
- The `rag-runtime` tool provider references `vectorio_provider: milvus` but the vector_io section may be missing or inline
- File uploads to vector stores use embedded SQLite instead of the standalone Milvus service
- Data is lost when the pod restarts (no persistent Milvus)

**Our chart fixes this** by using `milvus.mode` (a simple value `inline` or `remote`) instead of namespace-based conditionals. Works in any namespace.

### Genaiops Chart Missing vector_io Provider

Even when the genaiops chart includes `vector_io` in the `apis` list and the `rag-runtime` references `vectorio_provider: milvus`, the actual `vector_io` provider section may be missing from `providers` due to the namespace conditional. This causes:
```
RuntimeError: Failed to resolve 'tool_runtime' provider 'rag-runtime':
required dependency 'vector_io' is not available
```
Fix: ensure the vector_io provider is always included when rag is enabled (our chart does this).

### Custom Image and the Operator

The `LlamaStackDistribution` CR uses `distribution.image` (not `distribution.name`) to specify a custom image. If you set `distribution.name` AND a custom image, the operator ignores the image. Only one should be set:
```yaml
distribution:
  image: "quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3"  # guardrails
  # OR
  name: rh-dev  # default, NOT both
```

### `remote::trusty_fms` Is NOT Upstream

The `trusty_fms` safety provider only exists in the custom FMS image (`quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms`). It is NOT available in the standard `rh-dev` image. Deploying with `guardrails.enabled=true` on the standard image causes: `ValueError: Provider 'remote::trusty_fms' is not available for API 'Api.safety'`.

### `remote::passthrough` Does NOT Work with IBM Detectors

The upstream Llama Stack `remote::passthrough` safety provider calls `/moderations` (OpenAI format). IBM guardrails detectors use `/api/v1/text/contents` (different API). They are incompatible. Use `remote::trusty_fms` instead.

### Route Timeouts for File Uploads

OpenShift routes default to 30-second timeout. File uploads with embedding can exceed this for large files. Always annotate the route:
```bash
oc annotate route llama-stack haproxy.router.openshift.io/timeout=300s
```

### Empty `embedding_dimension` Breaks Vector Store Creation

The `/v1/vector_stores` API requires `embedding_dimension` as an integer. An empty string (`""`) causes `400 Bad Request`. The UI code handles this by omitting the field when empty.

### Model Names Change Between Charts

The genaiops chart names vLLM providers as `vllm-<model>` (e.g. `vllm-llama32/llama32`). Our chart uses `vllm` (e.g. `vllm/llama32`). After switching charts, users must re-select the model in Settings.

### Helm Release Conflicts with Manually Created Routes

If you manually `oc create route` for llama-stack, then `helm upgrade` will fail with "cannot import into current release". Delete the manual route before upgrading: `oc delete route llama-stack -n <namespace>`.

### Gemma 3n Produces Empty Output on RHOAI vLLM

`gemma-3n-e4b` (registered in vLLM as `Gemma3nForConditionalGeneration` — multimodal, hybrid attention/SSM architecture) generates `completion_tokens > 0` but `content: ""` on the RHOAI-shipped vLLM images (`0.13.0+rhai11`, `0.11.2+rhai5`). The text decoder for the hybrid architecture is not wired up correctly. Confirmed via direct `/v1/completions` (chat template not involved). **Workaround: stay on a `ForCausalLM` model** (Qwen2.5/Qwen3, Llama3, etc.) until a newer RHOAI vLLM image lands.

### Qwen3 `<think>...</think>` Blocks Eat Token Budget

`redhataiqwen3-8b-fp8-dynamic` and other Qwen3 variants emit a `<think>...</think>` reasoning trace before the user-facing response, consuming most of `max_tokens`. `extra_body: chat_template_kwargs.enable_thinking=false` is silently dropped by Llama Stack. `/no_think` system prompt only emits an empty `<think></think>` shell. Reliable fixes: (a) configure vLLM with `--reasoning-parser qwen3`, (b) strip `<think>...</think>` in the UI, or (c) switch to a non-thinking model like `qwen25-7b-instruct`.

### `vllm.modelId` Required, and Model is Prefixed with `vllm/`

Llama Stack auto-registers the embedding model from `inline::sentence-transformers` but **not** the vLLM-served LLM. Without `vllm.modelId` set in our chart, `/v1/models` only returns embedding models, and chat completions fail with `400 Bad Request: model field expected string`. After registration, the LLM is exposed with a `vllm/` prefix (e.g. `vllm/qwen25-7b-instruct`) — UIs must use the prefixed identifier.

### `tls_verify` Required in Guardrails-Mode vLLM Provider Config

OpenShift InferenceServices expose vLLM via kube-rbac-proxy on port 8443 with self-signed TLS. The non-guardrails llama-stack config block in our chart had `tls_verify: false` from the start; the guardrails-enabled block was missing it for a while, causing `APIConnectionError 500` on every chat completion despite curl from the pod working fine. Always check both config blocks contain `tls_verify` when editing the chart.

## Model Selection by Use Case

Measured on the available RHOAI vLLM build with `qwen25-7b-instruct` and `gpt-oss-20b`. Full numbers, methodology, and the benchmark recipe live in [`wiki/model-benchmarks.md`](wiki/model-benchmarks.md).

| Use case | Recommended | Why |
|----------|-------------|-----|
| Voice agent (STT → LLM → TTS) | `qwen25-7b-instruct` | TTFT to user-visible content ~45 ms (vs ~500 ms for gpt-oss). gpt-oss reasons silently before any content token, which becomes audible dead air. Multilingual coverage (Arabic, Urdu, Hindi, Indonesian) is also stronger than gpt-oss. |
| Plain text chat (streaming UI) | `qwen25-7b-instruct` | Same TTFT argument — characters start appearing immediately, which feels responsive. |
| Long RAG answers | `gpt-oss-20b` | ~3× higher throughput (98 vs 30 tok/s). The TTFT penalty amortizes over a long response. |
| Agent / tool-using flows | `gpt-oss-20b` | Hidden chain-of-thought improves tool selection and multi-step planning. |
| Multilingual (Arabic, Urdu, Hindi, Indonesian) | `qwen25-7b-instruct` | gpt-oss is English-first. |

**Reasoning models stream a separate field.** `gpt-oss-20b` (and Qwen3) emit chain-of-thought tokens in `delta.reasoning_content` (and a legacy `delta.reasoning`), not `delta.content`. A UI that only reads `delta.content` will appear frozen until the model finishes reasoning. If you stream from a reasoning model, surface the reasoning under a collapsible or skip it explicitly — don't ignore it.

**Routing pattern for production.** Both InferenceServices can run side-by-side. Llama Stack registers them as separate model IDs (`vllm/qwen25-7b-instruct`, `vllm/gpt-oss-20b`), so a router in your application can pick per turn — short conversational input → qwen25, longer or tool-flagged input → gpt-oss. No infrastructure changes needed.

## OpenShift Environment

### Cluster Access

Credentials in `.env`:
```bash
source .env
oc login -u $OC_USER -p $OC_PASSWORD https://api.$CLUSTER_DOMAIN:6443 --insecure-skip-tls-verify
```

### Key Namespaces

- `user1-canopy` — Llama Stack, Milvus, Guardrails Orchestrator, Dashy
- `ai501` — Shared services: vLLM models, guardrails detectors, embedding models, Docling

### Finding Services on a New Cluster

```bash
# vLLM InferenceServices
oc get inferenceservice -A

# Guardrails detectors
oc get inferenceservice -A | grep -iE "guard|hap|inject|language"

# Services and routes
oc get svc -A | grep -iE "vllm|llama|predictor|guard|milvus"
oc get route -A | grep -iE "vllm|llama|guard"
```

### Guardrails Detector Internal URLs

| Detector | Internal URL |
|----------|-------------|
| HAP | `http://guardrails-detector-ibm-hap-predictor.ai501.svc:8000` |
| Prompt Injection | `http://prompt-injection-detector-predictor.ai501.svc:8000` |
| Language | `http://language-detector-predictor.ai501.svc:8000` |

These are only accessible from inside the cluster. The guardrails orchestrator calls them internally.

## Reference Links

- Red Hat Llama Stack docs: `https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.0/html-single/working_with_llama_stack/index`
- OpenDataHub Llama Stack: `https://opendatahub.io/docs/working-with-llama-stack/`
- GenAIOps Helm Charts: `https://rhoai-genaiops.github.io/genaiops-helmcharts/`
- Red Hat lab example: `https://github.com/burrsutter/fantaco-redhat-one-2026`
- Llama Stack K8s Operator: `https://github.com/llamastack/llama-stack-k8s-operator`
- Llama Stack Safety docs: `https://llamastack.github.io/docs/building_applications/safety`
