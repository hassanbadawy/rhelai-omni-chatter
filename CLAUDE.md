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

## Repository Structure

```
├── helm/
│   ├── llama-stack/          # Llama Stack chart (guardrails + milvus + RAG)
│   ├── anythingllm/
│   ├── dashy/
│   ├── langflow/
│   ├── milvus/
│   ├── minio/
│   ├── n8n/
│   ├── postgresql-stack/
│   └── qdrant/
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
│   ├── config.yaml           # Runtime config (endpoint, model, shields, etc.)
│   └── docs/                 # API improvement docs
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

- `milvus.mode=inline` (default) — embedded Milvus with SQLite, no external service
- `milvus.mode=remote` — connects to standalone Milvus service, default token `root:Milvus`

### Helm Repo

Published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`. Chart packages are stored as GitHub Releases, `index.yaml` on `gh-pages` branch.

```bash
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install llama-stack hassanbadawy/llama-stack
```

To publish a new version: bump `Chart.yaml` version, `helm package`, `gh release create`, update `gh-pages` index.yaml via `helm repo index --merge`.

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
| `language_detection` | language-detector | Non-English text |
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
