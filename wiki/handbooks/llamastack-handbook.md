# The Llama Stack Handbook

**A Zero-to-Hero Guide for Python Developers**

> Everything you need to know to design, build, deploy, scale, and operate production-grade GenAI systems on Llama Stack — from your laptop to OpenShift, with agents, RAG, MCP, vector stores, S3, guardrails, shields, telemetry, Grafana, Prometheus, Docling, and multi-agent orchestration.

---

## Front Matter

### About This Book

This handbook is designed to be **self-contained**. Share it with another LLM and it will have everything it needs to help you build on Llama Stack — no external lookups required.

### Note on the Rebrand

As of 2026, **`meta-llama/llama-stack` has been rebranded to OGX** (`ogx-ai/ogx`, "Open GenAI Stack"). The Python package on PyPI is still `llama-stack` / `llama-stack-client` for the stable 0.2.x and 0.3.x series, but the GitHub repository, internal modules (`ogx`, `ogx_api`, `ogx_client`), and CLI entry-point (`ogx`) reflect the new name. **All API patterns, run.yaml schema, provider names, and SDK conventions are unchanged.** This handbook uses both names interchangeably.

### Conventions

- `pip install llama-stack` and `uv pip install ogx` both work.
- `llama stack run` and `ogx stack run` are aliases.
- Code examples target Python 3.12+.
- Default server port is `8321`.

---

## Table of Contents

### Part I — Foundations
- Chapter 1. What Is Llama Stack?
- Chapter 2. Architecture: Server, Routers, Providers
- Chapter 3. The API Surface
- Chapter 4. Distributions: Pre-Bundled Configurations
- Chapter 5. Mental Model: Resources, Routing Tables, and the Registry

### Part II — Installation & Deployment
- Chapter 6. Local Install (pip / uv)
- Chapter 7. Docker / Podman
- Chapter 8. Kubernetes via the Llama Stack Operator
- Chapter 9. OpenShift / RHOAI
- Chapter 10. Configuration: `run.yaml` Deep Dive

### Part III — Python SDK Zero to Hero
- Chapter 11. Client Initialization
- Chapter 12. Inference: Chat, Streaming, OpenAI Compatibility
- Chapter 13. Models, Embeddings, Reranking
- Chapter 14. Conversations and the Responses API
- Chapter 15. Agents (Legacy and Modern)
- Chapter 16. Tool Calls and Structured Output

### Part IV — Core Capabilities
- Chapter 17. RAG and Vector Stores
- Chapter 18. Files, Documents, and Docling
- Chapter 19. Safety, Shields, and Moderations
- Chapter 20. MCP (Model Context Protocol)
- Chapter 21. Telemetry, Tracing, and Metrics
- Chapter 22. Eval, Scoring, and Post-Training

### Part V — Building a Production Mega-Project
- Chapter 23. Reference Architecture for a Multi-Agent System
- Chapter 24. MCP Mesh: Designing Tool Servers
- Chapter 25. RAG at Scale: Vector Store Selection and Tuning
- Chapter 26. S3/MinIO Storage Strategy
- Chapter 27. Guardrails and Shields in Production
- Chapter 28. Observability: OTEL → Jaeger / Grafana / Prometheus
- Chapter 29. Scalability, Multi-Tenancy, and HA
- Chapter 30. Multi-Agent Orchestration Patterns
- Chapter 31. Security, AuthN/AuthZ, Quotas

### Part VI — Reference
- Chapter 32. Full `run.yaml` Schema
- Chapter 33. Provider Catalog
- Chapter 34. CLI Reference
- Chapter 35. REST API Quick Reference
- Chapter 36. Troubleshooting & Pitfalls
- Chapter 37. Glossary

---

# Part I — Foundations

## Chapter 1. What Is Llama Stack?

Llama Stack is a **stateful, agentic API server** that exposes a unified REST API for the building blocks of GenAI applications: LLM inference, agents, safety, vector search, evaluation, batching, telemetry, and more. The same API works regardless of which backend you plug in — Ollama on your laptop, vLLM in your cluster, Fireworks/Together/Anthropic/OpenAI in the cloud, or AWS Bedrock / Azure OpenAI / IBM WatsonX in your enterprise.

Two ideas drive the design:

1. **Provider-agnostic APIs.** You write to `client.chat.completions.create(...)` once. Whether the request lands on Ollama, vLLM, OpenAI, or Bedrock is a deployment-time decision controlled by `run.yaml`.
2. **Composability.** Capabilities like RAG, safety shields, file processing, and tool calling are first-class APIs that compose with inference. You don't bolt them on — they're part of the stack.

### What it is **not**

- It is not an LLM. It does not host models — vLLM, Ollama, etc. do.
- It is not a fine-tuning framework, though it ships a `post_training` API that wraps torchtune.
- It is not an opinionated agent framework like LangChain. It exposes building blocks; you compose them.

### Three packages

The codebase splits into three Python packages:

| Package | Role |
|---|---|
| `ogx_api` | Thin: `Protocol` classes, Pydantic types, provider spec definitions. **Third-party providers depend only on this.** |
| `ogx` | Server: provider resolution, routing, storage, CLI, all built-in providers. |
| `ogx_ui` | Optional Next.js admin/playground web UI. |

---

## Chapter 2. Architecture: Server, Routers, Providers

### Request Flow

```
Client (HTTP or Python SDK)
  ↓
FastAPI Server  (AuthenticationMiddleware, QuotaMiddleware)
  ↓
Route Dispatch  (auto-discovered via fastapi_router_registry.py)
  ↓
Router          (looks up resource in RoutingTable, picks provider, enforces ACL)
  ↓
Provider Implementation
  ├── Inline provider  (in-process: e.g. inline::faiss, inline::llama-guard)
  └── Remote provider  (calls external service: e.g. remote::ollama, remote::vllm)
  ↓
External Service or Local Computation
```

### Inline vs Remote Providers

**Inline providers** run inside the Llama Stack server process. Useful when you want a single self-contained binary (FAISS in-memory, sentence-transformers embedding, Llama Guard via the inference provider, etc.).

```python
InlineProviderSpec(
    api=Api.inference,
    provider_type="inline::sentence-transformers",
    module="ogx.providers.inline.inference.sentence_transformers",
    config_class="...SentenceTransformersInferenceConfig",
    pip_packages=["torch", "sentence-transformers"],
)
```

**Remote providers** are HTTP adapters that translate the unified Llama Stack API into a downstream service's API.

```python
RemoteProviderSpec(
    api=Api.inference,
    adapter_type="ollama",
    provider_type="remote::ollama",
    module="ogx.providers.remote.inference.ollama",
    config_class="...OllamaImplConfig",
    pip_packages=["ollama", "aiohttp"],
)
```

### Auto-Routing: Resources and the Registry

Many APIs use auto-routing: a **RoutingTable** tracks which provider owns each resource (model, shield, vector_db, dataset…), and a **Router** dispatches requests to the right provider.

| Routing Table API | Router API |
|---|---|
| `Api.models` | `Api.inference` |
| `Api.shields` | `Api.safety` |
| `Api.datasets` | `Api.datasetio` |
| `Api.scoring_functions` | `Api.scoring` |
| `Api.benchmarks` | `Api.eval` |
| `Api.tool_groups` | `Api.tool_runtime` |
| `Api.vector_stores` | `Api.vector_io` |

When you call `client.chat.completions.create(model="ollama/llama3.2:3b", ...)`, the router looks up `ollama/llama3.2:3b` in `Api.models`, finds it is owned by `provider_id=ollama`, and dispatches to that provider's inference adapter.

---

## Chapter 3. The API Surface

The full list of APIs the server can expose (via `apis:` in `run.yaml`):

| API | Purpose |
|---|---|
| `inference` | Chat completions, embeddings, rerank |
| `safety` | Shield checks, moderations |
| `agents` | **Deprecated in 0.3.0** — create agents, sessions, turns |
| `responses` | OpenAI-compatible Responses API (stateful, agentic) |
| `vector_io` | Vector store operations (insert, query) |
| `tool_runtime` | Tool execution (web search, file search, code interpreter, MCP, RAG) |
| `files` | File upload and management |
| `file_processors` | Document parsing (PDF, DOCX, etc.) |
| `scoring` | Evaluation scoring functions |
| `eval` | Run evaluations on benchmarks/datasets |
| `datasetio` | Dataset management |
| `post_training` | Fine-tuning (SFT with LoRA/DoRA via torchtune) |
| `telemetry` | Tracing and metrics (OTEL) |
| `batches` | Offline batch processing |
| `interactions` / `messages` | OpenAI Assistants-style conversation management |

**Modern best practice (0.3.0+):** prefer `responses` over `agents`. The Responses API is stateful via `previous_response_id`, OpenAI-compatible, and folds tool calling, MCP, and file_search into a single endpoint.

---

## Chapter 4. Distributions: Pre-Bundled Configurations

A **distribution** ("distro") is a pre-built `run.yaml` bundling specific providers for a target environment. Distros live in `src/ogx/distributions/`.

### Available Distributions

| Distro | Inference | Vector IO | Notes |
|---|---|---|---|
| `starter` | Cerebras, Ollama, vLLM, Fireworks, Together, Bedrock, NVIDIA, OpenAI, Anthropic, Gemini, Groq, SambaNova, Azure, sentence-transformers, transformers | faiss, sqlite-vec, milvus, chromadb, pgvector, qdrant, weaviate, elasticsearch | Multi-provider, conditional activation by env var |
| `nvidia` | NVIDIA NIM | faiss | NeMo Guardrails for safety |
| `watsonx` | IBM WatsonX | — | Enterprise |
| `oci` | Oracle Cloud GenAI | — | Cloud-native |
| `rh-dev` | vLLM | — | Red Hat OpenShift AI default |
| `vllm` | remote::vllm | faiss | For self-hosted vLLM clusters |
| `ollama` | remote::ollama | faiss | Laptop / dev |

### How `starter` Conditionally Activates Providers

The `starter` distro uses `${env.X:+id}` syntax — a provider is only registered when its API-key env var is set:

```yaml
- provider_id: ${env.NVIDIA_API_KEY:+nvidia}    # active only if NVIDIA_API_KEY is set
  provider_type: remote::nvidia
  config:
    api_key: ${env.NVIDIA_API_KEY:=}
```

This lets you ship a single image and let users pick providers via environment variables.

---

## Chapter 5. Mental Model: Resources, Routing Tables, and the Registry

Every "thing" in Llama Stack is a **resource** owned by a **provider** and tracked in a **routing table**:

| Resource | Lives In | Routed By |
|---|---|---|
| Model | `models` table | `inference` API |
| Shield | `shields` table | `safety` API |
| Vector DB | `vector_dbs` table | `vector_io` API |
| Tool group | `tool_groups` table | `tool_runtime` API |
| Dataset | `datasets` table | `datasetio` API |
| Benchmark | `benchmarks` table | `eval` API |
| Scoring function | `scoring_functions` table | `scoring` API |

You can pre-register resources at startup via `registered_resources:` in `run.yaml`, or register them at runtime via the SDK (`client.models.register(...)`, `client.shields.register(...)`, etc.). The routing table is persisted in the metadata kvstore and survives restarts.

---

# Part II — Installation & Deployment

## Chapter 6. Local Install (pip / uv)

### Quickstart with pip

```bash
pip install llama-stack llama-stack-client
```

### Quickstart with uv (recommended)

```bash
# Install the starter distro with all extras
uv pip install ogx[starter]

# One-liner installer
curl -LsSf https://github.com/ogx-ai/ogx/raw/main/scripts/install.sh | bash
```

### Development Install

```bash
git clone https://github.com/ogx-ai/ogx.git
cd ogx
uv sync                  # creates .venv, installs all deps
uv pip install -e .      # editable install
```

### Run via CLI

```bash
# Start a distro
OLLAMA_URL=http://localhost:11434 llama stack run starter

# Or use the new entry point
OLLAMA_URL=http://localhost:11434 ogx stack run starter

# Custom run.yaml
llama stack run /path/to/run.yaml --port 8321

# Build a portable distro image
llama stack build --template ollama --image-type conda --image-name my-build
```

### As a Library (in-process, no HTTP server)

For low-latency embedded scenarios, run Llama Stack inside your Python process — no HTTP hop:

```python
from ogx.core.library_client import OGXAsLibraryClient

client = OGXAsLibraryClient(
    "fireworks",
    provider_data={"fireworks_api_key": "..."},
)
client.initialize()

# Use the same API as the HTTP client
print(client.models.list())
```

---

## Chapter 7. Docker / Podman

### Starter Distribution

```bash
docker run -it --pull always \
  -p 8321:8321 \
  -v ~/.llama:/root/.llama \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  llamastack/distribution-starter
```

### Ollama Distribution (single inference backend)

```bash
export INFERENCE_MODEL="meta-llama/Llama-3.1-8B-Instruct"
export LLAMA_STACK_PORT=8321
export OLLAMA_HOST=192.168.1.100

podman run -it \
  --user 1000 \
  -p $LLAMA_STACK_PORT:$LLAMA_STACK_PORT \
  -v ~/.llama:/root/.llama \
  llamastack/distribution-ollama:0.2.8 \
  --port $LLAMA_STACK_PORT \
  --env INFERENCE_MODEL=$INFERENCE_MODEL \
  --env OLLAMA_URL=http://$OLLAMA_HOST:11434
```

### vLLM Distribution

```bash
docker run -it \
  -p 8321:8321 \
  -e VLLM_URL=http://vllm-host:8000/v1 \
  -e INFERENCE_MODEL=meta-llama/Llama-3.1-8B-Instruct \
  llamastack/distribution-remote-vllm
```

### Compose a Local Stack (Llama Stack + vLLM + Milvus + Jaeger)

```yaml
# docker-compose.yml
services:
  vllm:
    image: vllm/vllm-openai:latest
    command: ["--model", "meta-llama/Llama-3.1-8B-Instruct", "--port", "8000"]
    ports: ["8000:8000"]
    deploy: {resources: {reservations: {devices: [{capabilities: [gpu]}]}}}

  milvus:
    image: milvusdb/milvus:latest
    ports: ["19530:19530"]
    environment:
      ETCD_USE_EMBED: "true"
      MINIO_USE_EMBED: "true"

  jaeger:
    image: cr.jaegertracing.io/jaegertracing/jaeger:2.14.0
    ports: ["16686:16686", "4317:4317", "4318:4318"]

  llama-stack:
    image: llamastack/distribution-starter
    depends_on: [vllm, milvus, jaeger]
    environment:
      VLLM_URL: http://vllm:8000/v1
      MILVUS_URL: http://milvus:19530
      OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger:4318
      TELEMETRY_SINKS: console,sqlite,otel_trace
    ports: ["8321:8321"]
    volumes: ["./run.yaml:/root/.llama/run.yaml"]
```

---

## Chapter 8. Kubernetes via the Llama Stack Operator

The community ships a CRD-based operator (`llamastack.io/v1alpha1`) that manages `LlamaStackDistribution` resources.

### Install the Operator

```bash
# Kustomize
git clone https://github.com/llamastack/llama-stack-k8s-operator.git
kubectl apply -k config/default

# Or one-shot manifest
kubectl apply -f https://raw.githubusercontent.com/llamastack/llama-stack-k8s-operator/main/release/operator.yaml

# Verify
kubectl get crd llamastackdistributions.llamastack.io
kubectl get deployment -n llama-stack-k8s-operator-system
```

### LlamaStackDistribution CR

```yaml
apiVersion: llamastack.io/v1alpha1
kind: LlamaStackDistribution
metadata:
  name: llamastack-sample
spec:
  replicas: 1
  server:
    distribution:
      name: starter         # OR use a custom image:
      # image: "quay.io/custom/llama-stack:latest"
    containerSpec:
      env:
        - name: OLLAMA_URL
          value: "http://ollama.ollama-ns.svc.cluster.local:11434"
        - name: VLLM_URL
          value: "http://vllm-predictor.ai-ns.svc:8080/v1"
    storage:
      size: "20Gi"
      mountPath: "/home/lls/.lls"
```

> **Important:** `distribution.name` and `distribution.image` are **mutually exclusive**. If you set both, the operator silently picks `name` and ignores `image`.

### Wiring a Custom `run.yaml`

Mount via ConfigMap:

```yaml
spec:
  server:
    containerSpec:
      env:
        - name: LLAMA_STACK_CONFIG
          value: /etc/lls/run.yaml
      volumeMounts:
        - name: run-config
          mountPath: /etc/lls
    volumes:
      - name: run-config
        configMap:
          name: my-run-config
```

---

## Chapter 9. OpenShift / RHOAI

OpenShift adds a few wrinkles beyond plain Kubernetes:

1. **Routes** for external HTTP access (instead of ingress).
2. **SCCs** (Security Context Constraints) — pods run with random UIDs by default.
3. **service-ca certificates** for in-cluster TLS — the cluster injects a service CA bundle that you must trust if you call other in-cluster HTTPS services.

### Login & Install

```bash
oc login -u $OC_USER -p $OC_PASSWORD https://api.$CLUSTER_DOMAIN:6443

# Install operator from web console: Operators → OperatorHub → "Llama Stack"
# Or via CLI:
oc apply -f llamastack-operator.yaml -n <namespace>

# Apply the LlamaStackDistribution CR
oc apply -f llamastack-distribution.yaml -n <namespace>

# Inspect
oc get llamastackdistribution -n <namespace>
oc get pods -n <namespace>
oc get route llama-stack -n <namespace>
```

### Route Timeout for File Uploads

OpenShift HAProxy routes default to a 30-second timeout. Large file uploads with embedding can blow past that. Always annotate:

```bash
oc annotate route llama-stack haproxy.router.openshift.io/timeout=300s
```

### Trusting the OpenShift service-ca for Downstream HTTPS

If Llama Stack calls other cluster services over HTTPS (e.g. KServe predictors on `:8443`), it must trust the OpenShift service CA. Mount the cluster's `service-ca.crt` ConfigMap and append it to the system CA bundle in an init container, then point Python (`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`) at the combined bundle.

### RHOAI 3.0 Specifics

- The default distribution name is `rh-dev`.
- The custom FMS distribution uses `image: "quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3"` with `external_providers_dir: /opt/app-root/src/.llama/providers.d/`. Required to enable `remote::trusty_fms` (IBM Guardrails Orchestrator integration).
- Setting `distribution.image` overrides `distribution.name`. Don't set both.

### Common Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Provider 'remote::trusty_fms' is not available` | Wrong image | Use the FMS image, set `external_providers_dir` |
| `cannot import into current release` on `helm upgrade` | A manually-created Route conflicts with chart-managed Route | `oc delete route <name>` then re-upgrade |
| File upload times out at 30s | Default route timeout | Annotate route with `timeout=300s` |
| 400 on vector-store create with `embedding_dimension=""` | API requires int | Omit empty value, or send int |

---

## Chapter 10. Configuration: `run.yaml` Deep Dive

`run.yaml` is the single source of truth for a Llama Stack server. Modern (0.3.x) schema:

```yaml
version: 2
distro_name: starter
apis:
  - inference
  - safety
  - responses
  - vector_io
  - tool_runtime
  - files
  - file_processors
  - batches
providers:
  inference:
    - provider_id: ollama
      provider_type: remote::ollama
      config:
        base_url: ${env.OLLAMA_URL:=http://localhost:11434/v1}
  vector_io:
    - provider_id: faiss
      provider_type: inline::faiss
      config:
        persistence:
          namespace: vector_io::faiss
          backend: kv_default
storage:
  backends:
    kv_default:
      type: kv_sqlite
      db_path: ${env.SQLITE_STORE_DIR:=~/.ogx/distributions/starter}/kvstore.db
    sql_default:
      type: sql_sqlite
      db_path: ${env.SQLITE_STORE_DIR:=~/.ogx/distributions/starter}/sql_store.db
  stores:
    metadata: {namespace: registry, backend: kv_default}
    inference: {table_name: inference_store, backend: sql_default}
    conversations: {table_name: openai_conversations, backend: sql_default}
    prompts: {table_name: prompts, backend: sql_default}
registered_resources:
  models:
    - model_id: meta-llama/Llama-3.1-8B-Instruct
      provider_id: ollama
      provider_model_id: llama3.1:8b-instruct-fp16
      model_type: llm
  shields: []
  vector_dbs: []
server:
  port: 8321
```

### Older Schema (pre-0.3) — When to Use It

Older Red Hat / vLLM deployments and the FMS image use a different schema:

```yaml
version: 2
image_name: vllm
apis: [inference, safety, agents, vector_io, telemetry, tool_runtime]
providers:
  inference:
    - provider_id: vllm
      provider_type: remote::vllm
      config:
        url: http://vllm:8000/v1            # NOTE: 'url', not 'base_url'
        max_tokens: 4096
        api_token: fake
  vector_io:
    - provider_id: faiss
      provider_type: inline::faiss
      config:
        embedding_model: all-MiniLM-L6-v2
        embedding_dimension: 384
metadata_store:
  namespace: llamastack
  type: sqlite
  db_path: ~/.llama/distributions/vllm/registry.db
```

> **Critical pitfall:** the two schemas are **not mixable**. The FMS image rejects the `storage:` block with `ValidationError`; the modern image rejects `metadata_store:` style kvstore entries. Pick the schema that matches your image and stick with it.

### Env Var Substitution Syntax

| Form | Meaning |
|---|---|
| `${env.X:=default}` | Use `X`, fallback to `default` if unset |
| `${env.X:=}` | Use `X`, fallback to empty string |
| `${env.X:+id}` | Use `id` only when `X` is set; empty otherwise (used to conditionally activate providers) |

### Storage Backend Options

| Backend | Type | Use Case |
|---|---|---|
| `kv_sqlite` | KVStore | Default single-node |
| `kv_redis` | KVStore | Multi-node, caching |
| `kv_postgres` | KVStore | Production |
| `kv_mongodb` | KVStore | Document-oriented |
| `sql_sqlite` | SqlStore | Default single-node |
| `sql_postgres` | SqlStore | Production |

> **Production rule:** swap `kv_sqlite`/`sql_sqlite` for `kv_postgres`/`sql_postgres` as soon as you replicate the server (e.g. `replicas: 2`). SQLite is single-writer.

# Part III — Python SDK Zero to Hero

## Chapter 11. Client Initialization

```python
from llama_stack_client import LlamaStackClient, AsyncLlamaStackClient

# Synchronous client
client = LlamaStackClient(base_url="http://localhost:8321")

# Async
async_client = AsyncLlamaStackClient(base_url="http://localhost:8321")

# As library (in-process)
from ogx.core.library_client import OGXAsLibraryClient
client = OGXAsLibraryClient("starter")
client.initialize()
```

### Per-Request Provider Credentials

Pass downstream API keys at runtime — useful for multi-tenant SaaS where each user has their own keys:

```python
client = LlamaStackClient(
    base_url="http://localhost:8321",
    provider_data={
        "fireworks_api_key": user_keys["fireworks"],
        "tavily_search_api_key": user_keys["tavily"],
        "mcp_headers": {
            "http://mcp-server/sse": {"Authorization": f"Bearer {user_token}"}
        },
    },
)
```

### Health and Discovery

```python
client.inspect.health()         # {"status": "OK"}
client.inspect.version()        # {"version": "0.3.0"}
client.providers.list()         # all configured providers
client.models.list()            # registered models
client.shields.list()           # registered shields
```

---

## Chapter 12. Inference: Chat, Streaming, OpenAI Compatibility

### OpenAI-Compatible Chat (preferred in 0.3.x)

```python
response = client.chat.completions.create(
    model="ollama/llama3.2:3b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a haiku about Python."},
    ],
    temperature=0.7,
    max_tokens=256,
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="ollama/llama3.2:3b",
    messages=[{"role": "user", "content": "Count to 10 slowly."}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

### Legacy Inference API

```python
response = client.inference.chat_completion(
    model_id="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Hi"}],
)
print(response.completion_message.content.text)
```

### Tool Calling (OpenAI-style)

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}]

response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Weather in Cairo?"}],
    tools=tools,
    tool_choice="auto",
)
tool_call = response.choices[0].message.tool_calls[0]
print(tool_call.function.name, tool_call.function.arguments)
```

---

## Chapter 13. Models, Embeddings, Reranking

### List & Filter Models

```python
models = client.models.list()
llms = [m for m in models if m.model_type == "llm"]
embeddings = [m for m in models if m.model_type == "embedding"]
```

### Register a Model at Runtime

```python
client.models.register(
    model_id="meta-llama/Llama-3.1-8B-Instruct",
    provider_id="ollama",
    provider_model_id="llama3.1:8b-instruct-fp16",
    model_type="llm",
)
```

### Embeddings

```python
resp = client.embeddings.create(
    model="nomic-ai/nomic-embed-text-v1.5",
    input=["Hello world", "Another sentence"],
)
for item in resp.data:
    print(len(item.embedding))      # 768 for nomic-embed
```

### Reranking

```python
reranked = client.inference.rerank(
    model="Qwen/Qwen3-Reranker-0.6B",
    query="What is LoRA?",
    documents=[
        "LoRA is a parameter-efficient fine-tuning method.",
        "Python is a programming language.",
    ],
    top_n=2,
)
```

---

## Chapter 14. Conversations and the Responses API

The Responses API replaces the legacy Agents API in 0.3.0+. It is OpenAI-compatible, stateful via `previous_response_id`, and folds tool calling, MCP, and file_search into a single endpoint.

### Single-Turn

```python
response = client.responses.create(
    model="openai/gpt-4o",
    input="What is the capital of France?",
    instructions="You are a helpful assistant.",
)
print(response.output_text)
print(response.id)              # save for multi-turn
```

### Multi-Turn (stateful)

```python
r1 = client.responses.create(
    model=MODEL,
    input="What parks are in Rhode Island?",
    instructions="You help with US National Parks.",
    tools=[{
        "type": "mcp",
        "server_url": "http://localhost:3005/sse/",
        "server_label": "NPS",
        "requires_approval": False,
    }],
)

r2 = client.responses.create(
    model=MODEL,
    input="Which has the most events?",
    previous_response_id=r1.id,         # ← carries context
    tools=[{
        "type": "mcp",
        "server_url": "http://localhost:3005/sse/",
        "server_label": "NPS",
        "requires_approval": False,
    }],
)
print(r2.output_text)
```

### Streaming

```python
stream = client.responses.create(
    model=MODEL,
    input="Tell me a long story.",
    stream=True,
    temperature=0.7,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
```

### Multi-Tool (file_search + MCP + web)

```python
response = client.responses.create(
    model=MODEL,
    input="Find recent news on AI safety; cross-reference with our docs.",
    tools=[
        {"type": "file_search", "vector_store_ids": [vs.id]},
        {"type": "mcp", "server_url": "http://snow:8000/mcp",
         "server_label": "snow", "require_approval": "never",
         "headers": {"SERVICE_NOW_TOKEN": tok}},
        "builtin::websearch",
    ],
)
```

### Response Object

```python
response.id              # str — pass as previous_response_id
response.status          # "completed" | "failed" | ...
response.output_text     # str — convenience text accessor
response.output          # list of typed output items:
                         #   {"type": "message", "content": [...]}
                         #   {"type": "mcp_list_tools", ...}
                         #   {"type": "mcp_call", "name": ..., "output": ...}
                         #   {"type": "file_search_call", "queries": [...], "results": [...]}
```

### Manage Responses

```python
client.responses.retrieve(response_id)
client.responses.list(limit=10)
client.responses.delete(response_id)
```

### Guardrails on Responses

```python
response = client.responses.create(
    model=MODEL,
    input="Some risky question",
    extra_body={"guardrails": ["content_safety", "prompt_injection"]},
)
```

---

## Chapter 15. Agents (Legacy and Modern)

> **Status:** the Agents API is **deprecated as of 0.3.0**, but still functional. New code should use the Responses API. Legacy code is documented here for completeness.

### High-Level `Agent` Class

```python
from llama_stack_client import Agent, AgentEventLogger

agent = Agent(
    client,
    model="meta-llama/Llama-3.3-70B-Instruct",
    instructions="You are a helpful assistant.",
    tools=["builtin::websearch"],
    sampling_params={"strategy": {"type": "top_p", "temperature": 1.0, "top_p": 0.9}},
)

session_id = agent.create_session("my-session")

# Non-streaming
resp = agent.create_turn(
    messages=[{"role": "user", "content": "What is the weather?"}],
    session_id=session_id,
    stream=False,
)
print(resp.output_message.content)

# Streaming with event logger
stream = agent.create_turn(
    messages=[{"role": "user", "content": "Search for AI news"}],
    session_id=session_id,
)
for log in AgentEventLogger().log(stream):
    log.print()
```

### Tools — Three Forms

```python
# 1. Pre-registered toolgroup ID
tools=["builtin::websearch", "mcp::filesystem"]

# 2. Toolgroup with args
tools=[{"name": "builtin::rag", "args": {"vector_db_ids": ["my_db"]}}]

# 3. MCP server inline
tools=[{
    "type": "mcp",
    "server_url": "http://localhost:3005/sse/",
    "server_label": "NPS",
    "authorization": "bearer_token",
    "requires_approval": False,
    "headers": {"Authorization": "Bearer token"},
}]
```

### Document Attachments

```python
attachments = [
    {"content": {"uri": "https://example.com/doc.txt"}, "mime_type": "text/plain"},
]
resp = agent.create_turn(
    messages=[{"role": "user", "content": "Summarize."}],
    session_id=session_id,
    documents=attachments,
    stream=False,
)
```

### Parallel Workers

```python
from concurrent.futures import ThreadPoolExecutor
import uuid

def run_task(task):
    a = Agent(client, model=MODEL, instructions="...")
    sid = a.create_session(f"worker_{uuid.uuid4()}")
    r = a.create_turn(
        messages=[{"role": "user", "content": task}],
        session_id=sid, stream=False,
    )
    return r.output_message.content

with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(run_task, tasks))
```

### Low-Level Agents API

```python
ag = client.agents.create(agent_config={
    "model": MODEL,
    "instructions": "You are a helpful assistant",
    "toolgroups": ["builtin::websearch"],
    "tool_choice": "auto",
    "input_shields": [],
    "output_shields": [],
    "max_infer_iters": 10,
    "enable_session_persistence": False,
    "sampling_params": {"strategy": {"type": "top_p", "temperature": 1.0, "top_p": 0.9}},
})
session = client.agents.session.create(ag.agent_id, session_name="s1")
turn = client.agents.turn.create(
    agent_id=ag.agent_id,
    session_id=session.session_id,
    messages=[{"role": "user", "content": "Hi"}],
    stream=False,
)
```

---

## Chapter 16. Tool Calls and Structured Output

### Pydantic-Schema Output

```python
from pydantic import BaseModel

class Classification(BaseModel):
    reasoning: str
    support_team: str

agent = Agent(
    client,
    model=MODEL,
    instructions="Classify the support query and explain.",
    response_format={
        "type": "json_schema",
        "json_schema": Classification.model_json_schema(),
    },
)
resp = agent.create_turn(
    messages=[{"role": "user", "content": "My internet is down."}],
    session_id=agent.create_session("c1"),
    stream=False,
)
parsed = Classification.model_validate_json(resp.output_message.content)
```

### Builtin Toolgroups

| Toolgroup | Backed By |
|---|---|
| `builtin::websearch` | Brave / Bing / Tavily |
| `builtin::rag` | inline vector_io provider |
| `builtin::file_search` | inline::file-search |
| `builtin::wolfram_alpha` | remote::wolfram-alpha |
| `builtin::code_interpreter` | inline::code-interpreter |

---

# Part IV — Core Capabilities

## Chapter 17. RAG and Vector Stores

### Vector IO Providers

| Provider | Mode | Notes |
|---|---|---|
| `inline::faiss` | In-process | Vector search only; no keyword/hybrid |
| `inline::sqlite-vec` | In-process | Disk-based via SQLite extension |
| `inline::milvus` | In-process | Embedded `.db` file |
| `inline::chromadb` | In-process | ChromaDB embedded |
| `inline::qdrant` | In-process | Qdrant embedded |
| `remote::chromadb` | Remote | ChromaDB server |
| `remote::pgvector` | Remote | PostgreSQL + pgvector |
| `remote::qdrant` | Remote | Qdrant server |
| `remote::milvus` | Remote | Milvus server — **requires `token` (default `root:Milvus`)** |
| `remote::weaviate` | Remote | Weaviate |
| `remote::elasticsearch` | Remote | ES with vector support |
| `remote::infinispan` | Remote | Infinispan |

### Register a Vector DB

```python
import uuid

vp = [p for p in client.providers.list() if p.api == "vector_io"][0]

vector_db_id = f"docs_{uuid.uuid4()}"
client.vector_dbs.register(
    vector_db_id=vector_db_id,
    embedding_model="nomic-embed-text-v1.5",
    embedding_dimension=768,
    provider_id=vp.provider_id,
)
```

### Insert Documents via the RAG Tool

```python
from llama_stack_client.types import Document

docs = [
    Document(
        document_id="doc-1",
        content="https://raw.githubusercontent.com/pytorch/torchtune/main/docs/source/tutorials/lora_finetune.rst",
        mime_type="text/plain",
        metadata={},
    ),
    Document(
        document_id="doc-2",
        content="Plain text content of the document...",
        mime_type="text/plain",
        metadata={"source": "internal"},
    ),
]

client.tool_runtime.rag_tool.insert(
    documents=docs,
    vector_db_id=vector_db_id,
    chunk_size_in_tokens=512,
)
```

### Query

```python
# High-level (RAG tool)
res = client.tool_runtime.rag_tool.query(
    content="What is LoRA?",
    vector_db_ids=[vector_db_id],
)
for c in res.content:
    print(c.text)

# Low-level (vector_io)
res = client.vector_io.query(
    vector_db_id=vector_db_id,
    query="search query",
    params={"max_chunks": 5},
)
```

### OpenAI-Compatible Vector Stores API

```python
import requests
from io import BytesIO

resp = requests.get("https://www.paulgraham.com/greatwork.html")
buf = BytesIO(resp.content); buf.name = "greatwork.html"

f = client.files.create(file=buf, purpose="assistants")
vs = client.vector_stores.create(name="pg-essays", file_ids=[f.id])

results = client.vector_stores.search(vs.id, query="What is great work?")

# Add more files later
client.vector_stores.files.create(vs.id, file_id="file-xxx")
```

### Three RAG Patterns

**1. Agent + RAG tool:**

```python
rag_agent = Agent(
    client, model=MODEL,
    instructions="Answer based only on the provided documents.",
    tools=[{"name": "builtin::rag", "args": {"vector_db_ids": [vector_db_id]}}],
)
```

**2. Agent + file_search tool (Vector Store API):**

```python
agent = Agent(
    client, model=MODEL,
    instructions="You are a helpful assistant.",
    tools=[{"type": "file_search", "vector_store_ids": [vs.id]}],
)
```

**3. Manual pipeline (full control):**

```python
chunks = client.tool_runtime.rag_tool.query(
    content=question, vector_db_ids=[vector_db_id]
)
context = " ".join(str(c.text) for c in chunks.content)
prompt = f"Answer using only this context.\n<q>{question}</q>\n<ctx>{context}</ctx>"
ans = client.inference.chat_completion(
    model_id=model_id,
    messages=[{"role": "user", "content": prompt}],
)
```

### Tuning Knobs (`run.yaml > vector_stores`)

```yaml
vector_stores:
  default_provider_id: faiss
  default_embedding_model:
    provider_id: sentence-transformers
    model_id: nomic-ai/nomic-embed-text-v1.5
  default_reranker_model:
    provider_id: transformers
    model_id: Qwen/Qwen3-Reranker-0.6B
  file_ingestion_params:
    default_chunk_size_tokens: 512
    default_chunk_overlap_tokens: 128
  chunk_retrieval_params:
    chunk_multiplier: 5
    max_tokens_in_context: 4000
    default_reranker_strategy: rrf       # rrf | weighted | none
    rrf_impact_factor: 60.0
    weighted_search_alpha: 0.5
    default_search_mode: vector          # vector | keyword | hybrid
```

> **Search modes:** `vector` is dense-only; `keyword` is BM25; `hybrid` combines both with RRF or weighted fusion. Pure FAISS only supports `vector`. Milvus, ES, and Qdrant support all three.

---

## Chapter 18. Files, Documents, and Docling

### File Processor Providers

| Provider | Backend | Best For |
|---|---|---|
| `inline::auto` | pypdf + MarkItDown | Default — auto-routes by MIME |
| `inline::pypdf` | PyPDF | PDFs only |
| `inline::markitdown` | Microsoft MarkItDown | Multi-format, minimal ML deps |
| `inline::docling` | Docling (IBM Research) | Tables, headings, layout — structure-aware |
| `remote::docling-serve` | Docling Serve container | GPU-accelerated, scalable |

### `run.yaml` Config

```yaml
file_processors:
  - provider_id: docling-serve
    provider_type: remote::docling-serve
    config:
      base_url: ${env.DOCLING_SERVE_URL:=http://docling-serve:5001/v1}
      api_key: ${env.DOCLING_SERVE_API_KEY:=}
```

### Run Docling Serve

```bash
docker run -p 5001:5001 quay.io/docling-project/docling-serve
```

### Upload + Index Pipeline

```python
import requests
from io import BytesIO

pdf = requests.get("https://example.com/paper.pdf").content
buf = BytesIO(pdf); buf.name = "paper.pdf"

f = client.files.create(file=buf, purpose="assistants")
vs = client.vector_stores.create(name="papers", file_ids=[f.id])
# Docling parses → file_processors chunk → vector_io indexes
```

### Custom Pipeline (Docling → Llama Stack)

```python
# 1. Parse with Docling outside Llama Stack (e.g. in a notebook)
from docling.document_converter import DocumentConverter
doc = DocumentConverter().convert("paper.pdf").document
chunks = doc.chunks(max_tokens=512)

# 2. Insert into Llama Stack vector DB
client.tool_runtime.rag_tool.insert(
    documents=[
        Document(document_id=f"chunk-{i}", content=c.text,
                 mime_type="text/plain", metadata={"page": c.page})
        for i, c in enumerate(chunks)
    ],
    vector_db_id="papers",
    chunk_size_in_tokens=512,
)
```

---

## Chapter 19. Safety, Shields, and Moderations

### Available Safety Providers

| Provider | Type | Backend | Catches |
|---|---|---|---|
| `inline::llama-guard` | Inline | Llama Guard model via inference | Content moderation S1–S14 |
| `inline::prompt-guard` | Inline | PromptGuard-86M via transformers | Prompt injection |
| `inline::code-scanner` | Inline | `codeshield` lib | Code vulnerabilities |
| `remote::bedrock` | Remote | AWS Bedrock | AWS moderation |
| `remote::nvidia` | Remote | NVIDIA NeMo | NeMo Guardrails |
| `remote::passthrough` | Remote | Any `/moderations` endpoint | Custom (OpenAI format) |
| `remote::sambanova` | Remote | SambaNova via litellm | Multi-cat |
| `remote::trusty_fms` | Remote | IBM Guardrails Orchestrator | **FMS image only** |

### Llama Guard Categories (S1–S14)

```
S1  Violent Crimes              S8  Intellectual Property
S2  Non-Violent Crimes          S9  Indiscriminate Weapons
S3  Sex Crimes                  S10 Hate
S4  Child Exploitation          S11 Self-Harm
S5  Defamation                  S12 Sexual Content
S6  Specialized Advice          S13 Elections
S7  Privacy                     S14 Code Interpreter Abuse
```

`excluded_categories: []` means **all** categories active. To disable some:

```yaml
safety:
  - provider_id: llama-guard
    provider_type: inline::llama-guard
    config:
      excluded_categories: ["Elections", "Code Interpreter Abuse"]
```

### Register & Run Shields

```python
client.shields.register(
    shield_id="content_safety",
    provider_id="llama-guard",
    provider_shield_id="meta-llama/Llama-Guard-3-8B",
)

result = client.safety.run_shield(
    shield_id="content_safety",
    messages=[{"role": "user", "content": "How do I forge documents?"}],
    params={},
)
if result.violation:
    print(f"Blocked: {result.violation.user_message}")
```

### Moderations API (OpenAI-compatible)

```python
mod = client.moderations.create(
    input="Is this safe?",
    model="openai/gpt-3.5-turbo",
)
for r in mod.results:
    if r.flagged:
        print([k for k, v in r.categories.items() if v])
```

### Shields in Agents

```python
agent_config = {
    "model": MODEL,
    "instructions": "...",
    "input_shields": ["content_safety", "prompt_injection_check"],
    "output_shields": ["content_safety"],
}
```

### Guardrails in the Responses API

```python
client.responses.create(
    model=MODEL,
    input="...",
    extra_body={"guardrails": ["content_safety"]},
)
```

### IBM FMS Guardrails (`remote::trusty_fms`)

Only available in the custom FMS image (`quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3`). Speaks the IBM Guardrails Orchestrator API natively. Routes shield checks through the orchestrator to per-detector model services (HAP, prompt-injection, language-detection) plus a built-in regex detector.

```yaml
safety:
  - provider_id: trusty_fms
    provider_type: remote::trusty_fms
    config:
      orchestrator_url: http://guardrails-orchestrator.{{namespace}}.svc:8080
shields:
  - shield_id: hap
    provider_id: trusty_fms
    provider_shield_id: hap
  - shield_id: prompt_injection
    provider_id: trusty_fms
    provider_shield_id: prompt_injection
  - shield_id: language_detection
    provider_id: trusty_fms
    provider_shield_id: language_detection
    params:
      allowed_languages: ["en"]   # MUST set or every detection becomes a violation
  - shield_id: regex
    provider_id: trusty_fms
    provider_shield_id: regex
    params:
      patterns:
        - "(?i).*fight club.*"
        - "\\b\\d{3}-\\d{2}-\\d{4}\\b"
```

> **Pitfall:** `remote::passthrough` calls `/moderations` (OpenAI shape). IBM detectors expose `/api/v1/text/contents` (different shape). They are **incompatible** — use `remote::trusty_fms` instead.

---

## Chapter 20. MCP (Model Context Protocol)

MCP integration uses **SSE** (Server-Sent Events). Stdio MCP servers must be wrapped (e.g. via `supergateway`).

### Provider Config

```yaml
tool_runtime:
  - provider_id: model-context-protocol
    provider_type: remote::model-context-protocol
    config: {}
```

### Register an MCP Toolgroup

```bash
curl -X POST http://localhost:8321/v1/toolgroups \
  -H "Content-Type: application/json" \
  --data '{
    "provider_id": "model-context-protocol",
    "toolgroup_id": "mcp::filesystem",
    "mcp_endpoint": {"uri": "http://localhost:8002/sse"}
  }'
```

### Wrap a Stdio MCP Server as SSE

```bash
npx -y supergateway --port 8002 \
  --stdio "npx -y @modelcontextprotocol/server-filesystem /path/to/dir"
```

### Use MCP in an Agent

```python
agent = Agent(
    client, model=MODEL,
    instructions="You can use filesystem tools.",
    tools=[
        "mcp::filesystem",                   # pre-registered
        {                                    # inline definition
            "type": "mcp",
            "server_url": "http://localhost:3005/sse/",
            "server_label": "NPS",
            "authorization": "bearer_token",
            "requires_approval": False,
            "headers": {"Authorization": "Bearer token"},
        },
    ],
)
```

### Use MCP in the Responses API

```python
response = client.responses.create(
    model=MODEL,
    input="List parks in Rhode Island.",
    instructions="You are an NPS assistant.",
    tools=[{
        "type": "mcp",
        "server_url": "http://localhost:3005/sse/",
        "server_label": "NPS",
        "requires_approval": False,
        "authorization": os.environ["NPS_TOKEN"],
    }],
)
```

### Per-Request MCP Headers

```python
client = LlamaStackClient(
    base_url="http://localhost:8321",
    provider_data={
        "mcp_headers": {
            "http://mcp-server/sse": {"Authorization": f"Bearer {tok}"}
        }
    },
)
```

---

## Chapter 21. Telemetry, Tracing, and Metrics

### Providers

| Provider | Sinks |
|---|---|
| `inline::meta-reference` | `console`, `sqlite`, `otel_trace`, `otel_metric` |
| `remote::opentelemetry` | Forwards to external OTEL collector |

### `run.yaml` Config (legacy 0.2.x)

```yaml
telemetry:
  - provider_id: meta-reference
    provider_type: inline::meta-reference
    config:
      sqlite_db_path: ${env.SQLITE_STORE_DIR:=~/.llama}/trace_store.db
      sinks: ${env.TELEMETRY_SINKS:=console,sqlite,otel_trace}
      service_name: llama-stack
      otel_exporter_otlp_endpoint: ${env.OTEL_EXPORTER_OTLP_ENDPOINT:=}
```

### 0.3.x Env-Driven

```bash
export OTEL_SERVICE_NAME=llama-stack-service
export OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
export TELEMETRY_SINKS=console,sqlite,otel_trace
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
```

### Local Jaeger

```bash
docker run --rm --name jaeger \
  -p 16686:16686 -p 4317:4317 -p 4318:4318 \
  cr.jaegertracing.io/jaegertracing/jaeger:2.14.0
# UI: http://localhost:16686
```

### Custom OTEL Span Propagation (Python clients / MCP servers)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap, inject, extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
import os

provider = TracerProvider()
trace.set_tracer_provider(provider)

if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
    ))

set_global_textmap(TraceContextTextMapPropagator())
tracer = trace.get_tracer(__name__)

# Outbound: inject traceparent
headers = {}
inject(headers)
requests.post(downstream_url, headers=headers, json=payload)

# Inbound: extract incoming context
ctx = extract({k.lower(): v for k, v in dict(request.headers).items()})
with tracer.start_as_current_span("my.span", context=ctx) as span:
    span.set_attribute("user.id", user_id)
```

### Auto-Instrumentation

```python
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

HTTPXClientInstrumentor().instrument()
FastAPIInstrumentor.instrument_app(app)
```

---

## Chapter 22. Eval, Scoring, and Post-Training

### Scoring Functions

| Function | Use |
|---|---|
| `basic::equality` | Exact match |
| `basic::subset_of` | Substring match |
| `braintrust::factuality` | Factual accuracy via Braintrust |
| `llm-as-judge` | Score with another LLM |
| `regex_parser` | Extract scores by regex |

### Score Directly

```python
res = client.scoring.score(
    input_rows=[{
        "input_query": "Capital of France?",
        "expected_answer": "Paris",
        "generated_answer": "The capital of France is Paris.",
    }],
    scoring_functions={
        "basic::subset_of": None,
        "braintrust::factuality": None,
    },
)
```

### Eval API (full benchmark run)

```python
client.datasets.register(
    purpose="eval/question-answer",
    source={"type": "uri", "uri": "huggingface://datasets/llamastack/evaluation_dataset"},
    dataset_id="qa_eval",
)

client.benchmarks.register(
    benchmark_id="qa_bench",
    dataset_id="qa_eval",
    scoring_functions=["basic::equality", "braintrust::factuality"],
)

result = client.eval.run_eval(
    benchmark_id="qa_bench",
    eval_candidate={
        "type": "model",
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "sampling_params": {"max_tokens": 256, "temperature": 0.0},
    },
    num_examples=100,
)
```

### Post-Training (LoRA SFT via torchtune)

```yaml
post_training:
  - provider_id: torchtune
    provider_type: inline::torchtune
    config: {}
```

```python
job = client.post_training.supervised_fine_tune(
    model="meta-llama/Llama-3.1-8B-Instruct",
    training_config={"n_epochs": 3, "batch_size": 4, "dataset_id": "my_sft"},
    optimizer_config={"lr": 1e-4},
    algorithm_config={
        "type": "lora",
        "rank": 16, "alpha": 32, "dropout": 0.1,
        "target_modules": ["q_proj", "v_proj"],
    },
)
```

# Part V — Building a Production Mega-Project

This part walks through a realistic enterprise GenAI platform. The scenario:

> **You are building "OmniChatter," a multi-tenant assistant platform for a large enterprise. Tenants get an LLM-powered chat with their own document set, can register their own MCP tools, and the platform must enforce shields, log everything, scale to thousands of concurrent conversations, and run inside an air-gapped OpenShift cluster.**

## Chapter 23. Reference Architecture for a Multi-Agent System

### High-Level Diagram

```
                                    ┌────────────────┐
   Tenant 1 web/mobile → ──┐        │  Auth (OIDC)   │
   Tenant 2 web/mobile → ──┼──→ ┌───┴─────────┐      │
                            └──→ │ API Gateway │←─────┘
                                 │ (rate limit │
                                 │  + per-tenant
                                 │   quotas)   │
                                 └──┬──────────┘
                                    │
                              ┌─────┴───────┐
                              │ Llama Stack │  (HPA, 3+ replicas, Postgres-backed)
                              └─┬─┬─┬─┬─┬─┬─┘
                                │ │ │ │ │ │
                  ┌─────────────┘ │ │ │ │ └────────────────┐
                  │       ┌───────┘ │ │ └────┐             │
              vLLM(s)  Milvus  Guardrails  MCP        OTEL Collector
              (KServe) (HA)    Orchestrator Mesh      → Jaeger
                                              │       → Prometheus
                                              ↓       → Grafana
                                     ┌──────────────┐
                                     │ Tenant MCPs  │
                                     │ (per-tenant) │
                                     └──────────────┘

         Files →  S3 / MinIO   ←──── inline::localfs (PVC-backed) OR custom S3 provider
         Docling Serve (GPU)   ←──── file_processors: remote::docling-serve
         PostgreSQL (HA)       ←──── kv/sql backends, conversation history
         Redis Cluster         ←──── kv_redis for hot-path caching
```

### Component Responsibilities

| Component | Role |
|---|---|
| API Gateway | OIDC auth, per-tenant rate limit, JWT enrichment, route to LS |
| Llama Stack (3+ replicas) | Stateless API surface; all state in Postgres/Redis |
| vLLM (KServe `InferenceService`) | LLM inference, GPU-pooled |
| Milvus (HA) | Shared vector store with per-tenant collections |
| Guardrails Orchestrator | HAP, prompt-injection, language, regex shields |
| MCP Mesh | Per-tenant SSE servers (filesystem, ServiceNow, JIRA, etc.) |
| Docling Serve | GPU-backed document parser |
| PostgreSQL (HA) | Conversations, registry, file metadata |
| Redis Cluster | Hot KV cache, model/tool registry caching |
| MinIO/S3 | File storage |
| OTEL Collector | Trace + metric fan-out |

### Multi-Tenant Isolation Patterns

| Resource | Isolation Strategy |
|---|---|
| Vector DB | One Milvus collection per tenant: `vec__{tenant_id}` |
| Files | S3 prefix per tenant: `s3://files/{tenant_id}/...` |
| Conversations | `tenant_id` column in Postgres tables |
| MCP servers | Distinct `server_label` and `provider_data.mcp_headers` per request |
| Shields | Same shield IDs but per-tenant override params via `extra_body` |
| Quotas | Enforced at gateway by tenant-id claim |

---

## Chapter 24. MCP Mesh: Designing Tool Servers

### Naming and Discovery

Use a stable naming scheme so tools are addressable in run.yaml or per-request:

```
mcp::{domain}.{tool}      # e.g. mcp::servicenow.tickets
mcp::{tenant}.{tool}      # e.g. mcp::acme.calendar
```

### Authentication Pattern

Pass tenant-scoped tokens via `provider_data` so a single Llama Stack instance can fan out across many tenants:

```python
client = LlamaStackClient(
    base_url=LS_URL,
    provider_data={
        "mcp_headers": {
            "http://mcp-snow:8000/mcp": {"Authorization": f"Bearer {tenant.snow_token}"},
            "http://mcp-jira:8000/mcp": {"Authorization": f"Bearer {tenant.jira_token}"},
        }
    },
)
```

### Approval Mode

For destructive tools, set `requires_approval: True`. The Responses API will pause and emit an `mcp_call_approval_request` item that your UI must surface to the human:

```python
client.responses.create(
    model=MODEL,
    input="Close all P3 tickets older than 30 days.",
    tools=[{
        "type": "mcp",
        "server_url": "http://mcp-snow:8000/mcp",
        "server_label": "snow",
        "requires_approval": True,
    }],
)
```

### MCP Server Best Practices

- **Idempotency keys** on side-effecting tool calls — LLMs retry.
- **Structured errors** with stable codes (`auth_failed`, `not_found`, `rate_limited`).
- **Pagination** for any list tool — never return >100 items unbounded.
- **Trace context propagation** — extract `traceparent` from headers, attach to outgoing calls.
- **Rate limit per `server_label`** — protect downstream APIs from runaway agents.

---

## Chapter 25. RAG at Scale: Vector Store Selection and Tuning

### Selection Matrix

| Need | Use |
|---|---|
| Single-process dev | `inline::faiss` |
| Single-node prod, simple | `inline::sqlite-vec` |
| Multi-tenant + hybrid search + filters | **`remote::milvus`** or `remote::elasticsearch` |
| Already running Postgres | `remote::pgvector` |
| Best-in-class hybrid + filters | `remote::qdrant` |
| Schema flexibility, GraphQL | `remote::weaviate` |

### Milvus Multi-Tenant Layout

```python
# Per-tenant collection
def vec_db_id(tenant_id): return f"vec__{tenant_id}"

client.vector_dbs.register(
    vector_db_id=vec_db_id(tenant_id),
    embedding_model="nomic-embed-text-v1.5",
    embedding_dimension=768,
    provider_id="milvus",
)
```

> **Milvus token:** the `remote::milvus` provider requires a `token` field (default `root:Milvus`). Without it the provider fails with `Field required`.

### Chunking Heuristics

- **Long-form prose:** 512 tokens, 128 overlap.
- **Code/technical docs:** 256 tokens, 64 overlap (smaller chunks → more precise retrieval).
- **Tables/structured:** parse with Docling first; treat each table row/section as its own chunk.
- **Multi-language:** chunk on sentence boundaries with language-aware splitter.

### Hybrid Search

```yaml
chunk_retrieval_params:
  default_search_mode: hybrid
  default_reranker_strategy: rrf
  rrf_impact_factor: 60.0
```

Reciprocal Rank Fusion (RRF) is the safe default — no tuning required. Use weighted (`alpha`) only if you have eval data showing one signal dominates.

### Reranker

Add a reranker for any RAG pipeline serving end users:

```yaml
default_reranker_model:
  provider_id: transformers
  model_id: Qwen/Qwen3-Reranker-0.6B
```

Returns the top-N with order optimized for relevance. Costs ~30–80 ms but typically lifts answer quality more than any other single change.

### Index Maintenance

- For HNSW (`pgvector`, `qdrant`, `milvus`): tune `m=16`, `ef_construction=64`, `ef_search=40` as a starting point. Increase `ef_search` for higher recall at the cost of latency.
- Schedule background re-indexing if you delete or update >5% of corpus.
- Track recall@K via the eval API as a regression metric.

---

## Chapter 26. S3/MinIO Storage Strategy

Llama Stack ships **no upstream `inline::s3` files provider** as of 0.3.x. The default is `inline::localfs` with a configurable `storage_dir`. Three production patterns:

### Pattern A — PVC-Backed `localfs`

Cheapest, simplest. Use a ReadWriteMany (RWX) PVC across replicas:

```yaml
files:
  - provider_id: builtin-files
    provider_type: inline::localfs
    config:
      storage_dir: /var/llama-stack/files
      metadata_store:
        table_name: files_metadata
        backend: sql_default
```

Limit: bound by RWX capability of your storage class. OK for single-cluster, dev/test, or workloads <10TB.

### Pattern B — MinIO Sidecar with `s3fs` Mount

Mount S3 bucket as a filesystem; the localfs provider reads from it transparently. Good for migration from local FS.

### Pattern C — Custom S3 Provider

Implement a custom files provider against `ogx_api`'s `Files` protocol that wraps boto3:

```python
class S3FilesProvider:
    async def upload_file(self, file): ...
    async def list_files(self): ...
    async def get_file(self, file_id): ...
    async def delete_file(self, file_id): ...
```

Register via `external_providers_dir`. Per-tenant prefix isolation:

```python
key = f"{tenant_id}/{file.id}"
self.s3.put_object(Bucket=BUCKET, Key=key, Body=file.read())
```

### MinIO HA Setup

```yaml
# 4-node distributed MinIO
services:
  minio-{1..4}:
    image: quay.io/minio/minio
    command: server http://minio-{1...4}/data/{1...2}
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
```

---

## Chapter 27. Guardrails and Shields in Production

### Defense in Depth

| Layer | Where | Purpose |
|---|---|---|
| Input shield | Before LLM call | Block obvious prompt injection, hate, illegal asks |
| RAG context shield | After retrieval, before prompt assembly | Filter out poisoned chunks |
| Output shield | After LLM response | Block leaks, unsafe content |
| Tool argument shield | Before MCP call | Validate destructive args (regex) |
| Audit shield | Async, post-flight | Sample for compliance review |

### Mixing Providers

Production typically combines:

- **Llama Guard** for content categories (S1–S14).
- **Prompt Guard** for prompt injection.
- **Trusty FMS** (HAP, language, regex) for IBM-stack environments.
- **Custom regex shields** for PII (SSN, emails, phones, custom patterns).

### Per-Tenant Override

```python
client.responses.create(
    model=MODEL, input=user_msg,
    extra_body={
        "guardrails": [
            "content_safety",
            "prompt_injection",
            f"regex_pii_{tenant.locale}",
        ],
    },
)
```

### Regex Shield Patterns

| Concern | Pattern |
|---|---|
| US SSN | `\b\d{3}-\d{2}-\d{4}\b` |
| Email | `\b[\w.-]+@[\w.-]+\.\w+\b` |
| US phone | `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` |
| Block keywords | `(?i).*(competitor|fight club).*` |

### Failure Modes

| Symptom | Likely Cause |
|---|---|
| `language_detection` flags everything | Missing `allowed_languages: ["en"]` in shield params (orchestrator treats any detection as a violation) |
| `Provider 'remote::trusty_fms' not available` | Standard `rh-dev` image — switch to FMS image |
| Shield latency >2s | Detector cold start — set min replicas ≥1 on the InferenceService |
| Shield false positives in RAG context | Shielding chunks individually; consider whole-doc shielding instead |

---

## Chapter 28. Observability: OTEL → Jaeger / Grafana / Prometheus

### Trace Plan

Every request should produce a trace with these spans:

```
http.request                       (FastAPI)
└── ls.responses.create             (router)
    ├── ls.shield.run (input)
    ├── ls.tool.rag.query
    │   └── ls.vector_io.query
    │       └── milvus.search       (downstream)
    ├── ls.inference.chat_completion
    │   └── vllm.chat               (downstream)
    ├── ls.shield.run (output)
    └── ls.persistence.write
```

### OTEL Collector → Multi-Backend

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      http: {endpoint: 0.0.0.0:4318}
      grpc: {endpoint: 0.0.0.0:4317}
exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls: {insecure: true}
  prometheus:
    endpoint: 0.0.0.0:8889
service:
  pipelines:
    traces:  {receivers: [otlp], exporters: [otlp/jaeger]}
    metrics: {receivers: [otlp], exporters: [prometheus]}
```

### Grafana Dashboards (recommended panels)

| Panel | PromQL |
|---|---|
| Requests/sec by tenant | `sum(rate(http_server_requests_total[5m])) by (tenant_id)` |
| p95 latency | `histogram_quantile(0.95, sum(rate(http_server_duration_bucket[5m])) by (le))` |
| Shield blocks | `sum(rate(ls_shield_violations_total[5m])) by (shield_id, severity)` |
| Tokens/sec | `sum(rate(ls_inference_tokens_total[5m])) by (model)` |
| RAG cache hit ratio | `sum(rate(ls_rag_cache_hits[5m])) / sum(rate(ls_rag_queries[5m]))` |
| MCP tool errors | `sum(rate(ls_mcp_call_errors_total[5m])) by (server_label, code)` |

### Alerts

```yaml
- alert: LlamaStackHighErrorRate
  expr: sum(rate(http_server_requests_total{status=~"5.."}[5m])) by (instance)
        / sum(rate(http_server_requests_total[5m])) by (instance) > 0.05
  for: 5m
- alert: ShieldOrchestratorDown
  expr: up{job="guardrails-orchestrator"} == 0
  for: 2m
- alert: VLLMQueueDepth
  expr: vllm_num_requests_waiting > 50
  for: 3m
```

### Logs

Structured JSON, with at minimum: `trace_id`, `span_id`, `tenant_id`, `request_id`, `model`, `provider`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`. Ship via Fluent Bit / Vector to Loki or Elastic.

---

## Chapter 29. Scalability, Multi-Tenancy, and HA

### Stateless Llama Stack Replicas

To run more than one replica:

1. Move all state to **`kv_postgres`** + **`sql_postgres`** (away from SQLite).
2. Move RAG index to **`remote::milvus`** / `remote::pgvector` / `remote::qdrant`.
3. Move files to S3 (custom provider) or RWX PVC.
4. Move telemetry SQLite to OTEL collector (`sinks: otel_trace`).

```yaml
storage:
  backends:
    kv_default:
      type: kv_postgres
      host: pg-primary
      database: llamastack
      user: ls
      password: ${env.PG_PASSWORD}
    sql_default:
      type: sql_postgres
      host: pg-primary
      database: llamastack_sql
      user: ls
      password: ${env.PG_PASSWORD}
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: llama-stack}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: llama-stack}
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 70}}
    - type: External
      external:
        metric: {name: ls_inflight_requests}
        target: {type: Value, averageValue: "20"}
```

### vLLM Pooling

- Run vLLM as a KServe `InferenceService` with autoscaling on `concurrency`.
- Use `tensor_parallel_size` for large models, `pipeline_parallel_size` only when memory-bound.
- For >1 model, run **one InferenceService per model** and register each as a separate provider in `run.yaml`. Don't multiplex.

### Caching Hot Reads

- `kv_redis` for the metadata store — model/shield/toolgroup lookups happen per request.
- Add a read-through cache for embeddings of common queries (e.g. Redis with TTL=24h).
- For semantic cache (response caching), embed the query, look up in a tiny Milvus collection by cosine ≥ 0.95.

### Tenant Quotas

Enforce at the gateway and inside Llama Stack:

```python
# Custom QuotaMiddleware reads tenant_id from JWT, increments a Redis counter,
# rejects with 429 above the limit.
```

---

## Chapter 30. Multi-Agent Orchestration Patterns

### Pattern 1 — Supervisor + Workers

```python
supervisor = Agent(
    client, model="meta-llama/Llama-3.3-70B-Instruct",
    instructions="Decompose the task and delegate sub-tasks to workers.",
    response_format={"type": "json_schema", "json_schema": Plan.model_json_schema()},
)
def run_worker(subtask):
    a = Agent(client, model="meta-llama/Llama-3.1-8B-Instruct",
              instructions=f"Specialist for: {subtask['skill']}")
    sid = a.create_session(f"w-{uuid.uuid4()}")
    return a.create_turn(messages=[{"role": "user", "content": subtask["input"]}],
                         session_id=sid, stream=False).output_message.content

plan = supervisor.create_turn(
    messages=[{"role": "user", "content": user_request}],
    session_id=supervisor.create_session("plan"),
    stream=False,
)
plan_obj = Plan.model_validate_json(plan.output_message.content)

with ThreadPoolExecutor(max_workers=8) as ex:
    sub_results = list(ex.map(run_worker, plan_obj.subtasks))

# Synthesize
final = supervisor.create_turn(
    messages=[{"role": "user", "content": f"Combine: {sub_results}"}],
    session_id=supervisor.create_session("synthesize"),
    stream=False,
)
```

### Pattern 2 — Pipeline (Plan → Retrieve → Reason → Cite)

Each stage is a separate Responses call linked via `previous_response_id`. Lets you switch models per stage (cheap retrieval, expensive reasoning).

### Pattern 3 — Critic Loop

Generator emits a draft; critic evaluates against rubric (via `scoring`); generator retries until critic accepts or N=3 retries hit.

### Pattern 4 — Parallel-Of-Thought

Run K agents on the same prompt at temperature ≥0.7, then select the best output via `llm-as-judge` scoring. Lifts quality significantly on hard reasoning tasks.

---

## Chapter 31. Security, AuthN/AuthZ, Quotas

### Authentication

Llama Stack server has built-in `AuthenticationMiddleware`:

- **API key** auth: simple, set `X-API-Key` header.
- **JWT/OIDC**: validate via JWKS; extract claims into request context.
- **mTLS**: terminate at the gateway/route.

Configure per-provider tokens via `provider_data` so user identity can flow into downstream API keys when needed.

### Authorization

- Vector DBs, files, conversations, shields all carry an `access_attributes` map.
- Configure router-level access control to filter resources by tenant claim.
- For multi-tenant, enforce that resource IDs always include the tenant prefix and the router rejects mismatched access.

### Secret Management

- Don't bake API keys into images. Use Kubernetes Secrets, OpenShift `ServiceAccount` tokens, or a secret manager (Vault, External Secrets, AWS SM).
- Rotate `LITELLM_MASTER_KEY`, `JWT_SECRET`, OAuth client secrets via the chart (`existingSecret` parameters).

### Threat Model — Top 5 Risks

1. **Prompt injection via RAG** → use Prompt Guard, sanitize tool descriptions, escape retrieved text in templates.
2. **Tool argument abuse** → require approval on destructive tools; regex-validate args.
3. **Data exfiltration via output** → output shields blocking secrets/PII.
4. **Token theft via shared MCP creds** → per-tenant `mcp_headers`, never share tokens across tenants.
5. **Cost blowups** → quotas + per-tenant budget limits + alert on `ls_cost_usd_total`.

---

# Part VI — Reference

## Chapter 32. Full `run.yaml` Schema

```yaml
version: 2                              # always 2
distro_name: starter                    # distribution name
image_name: my-build                    # optional container image name
apis:                                   # list of APIs to enable
  - inference
  - safety
  - responses
  - vector_io
  - tool_runtime
  - files
  - file_processors
  - batches
  - agents          # deprecated 0.3.0
  - datasetio
  - scoring
  - eval
  - post_training
  - telemetry
providers:
  <api>:
    - provider_id: <string>             # unique within this API
      provider_type: <inline::X | remote::X>
      config: {<key>: <value>}
storage:
  backends:
    kv_default:
      type: kv_sqlite | kv_redis | kv_postgres | kv_mongodb
      db_path: ...                      # for sqlite
      host: ...                         # for redis/postgres/mongodb
    sql_default:
      type: sql_sqlite | sql_postgres
      db_path: ...
  stores:
    metadata:      {namespace: registry,   backend: kv_default}
    inference:     {table_name: inference_store, backend: sql_default}
    conversations: {table_name: openai_conversations, backend: sql_default}
    prompts:       {table_name: prompts, backend: sql_default}
registered_resources:
  models:
    - model_id: <string>
      provider_id: <string>
      provider_model_id: <string|null>
      model_type: llm | embedding | reranker
      metadata: {}
  shields:
    - shield_id: <string>
      provider_id: <string>
      provider_shield_id: <string>
  vector_dbs: []
server:
  port: 8321
vector_stores:
  default_provider_id: faiss
  default_embedding_model:
    provider_id: sentence-transformers
    model_id: nomic-ai/nomic-embed-text-v1.5
  default_reranker_model:
    provider_id: transformers
    model_id: Qwen/Qwen3-Reranker-0.6B
  file_ingestion_params:
    default_chunk_size_tokens: 512
    default_chunk_overlap_tokens: 128
  chunk_retrieval_params:
    chunk_multiplier: 5
    max_tokens_in_context: 4000
    default_reranker_strategy: rrf      # rrf | weighted | none
    rrf_impact_factor: 60.0
    weighted_search_alpha: 0.5
    default_search_mode: vector         # vector | keyword | hybrid
external_providers_dir: /opt/app-root/src/.llama/providers.d/   # custom providers
metadata_store:                                                  # legacy schema only
  type: sqlite
  db_path: ~/.llama/.../registry.db
```

---

## Chapter 33. Provider Catalog

### Inference

```
inline::sentence-transformers     embeddings (nomic, MiniLM, BGE…)
inline::transformers              rerankers
remote::cerebras                  Cerebras Cloud
remote::ollama                    Ollama
remote::vllm                      vLLM (use `url`, not `base_url`, in legacy schema)
remote::fireworks                 Fireworks AI
remote::together                  Together AI
remote::bedrock                   AWS Bedrock
remote::nvidia                    NVIDIA NIM
remote::openai                    OpenAI
remote::anthropic                 Anthropic Claude
remote::gemini                    Google Gemini
remote::vertexai                  Google Vertex AI
remote::groq                      Groq
remote::sambanova                 SambaNova
remote::azure                     Azure OpenAI
remote::watsonx                   IBM WatsonX
remote::oci                       Oracle Cloud
remote::databricks                Databricks
remote::runpod                    RunPod
remote::llama-openai-compat       any OpenAI-compatible endpoint
remote::llama-cpp-server          llama.cpp server
remote::passthrough               any OpenAI-compatible endpoint
```

### Vector IO

```
inline::faiss          inline::sqlite-vec     inline::milvus
inline::chromadb       inline::qdrant
remote::chromadb       remote::pgvector       remote::qdrant
remote::milvus         remote::weaviate       remote::elasticsearch
remote::infinispan     remote::oci
```

### Safety

```
inline::llama-guard    inline::prompt-guard   inline::code-scanner
remote::bedrock        remote::nvidia         remote::passthrough
remote::sambanova      remote::trusty_fms (FMS image only)
```

### Tool Runtime

```
inline::file-search           builtin::file_search
remote::brave-search          builtin::websearch
remote::bing-search           builtin::websearch
remote::tavily-search         builtin::websearch
remote::wolfram-alpha         builtin::wolfram_alpha
remote::model-context-protocol  MCP
inline::rag-runtime           builtin::rag (legacy)
inline::code-interpreter      builtin::code_interpreter
```

### File Processors

```
inline::auto       inline::pypdf       inline::markitdown
inline::docling    remote::docling-serve
```

### Files

```
inline::localfs   (only upstream provider; S3 requires custom)
```

### Telemetry

```
inline::meta-reference   remote::opentelemetry
```

### Post-Training / Eval / Scoring

```
post_training:  inline::torchtune
eval:           inline::meta-reference
scoring:        inline::basic, inline::llm-as-judge, inline::braintrust, inline::regex_parser
batches:        inline::reference
datasetio:      inline::localfs, remote::huggingface
```

---

## Chapter 34. CLI Reference

```bash
# Launch a distro
llama stack run starter
llama stack run /path/to/run.yaml --port 8321

# Build a distro to a specific image type
llama stack build --template ollama --image-type conda --image-name my-build
llama stack build --template starter --image-type docker

# List distributions
llama stack list-distros

# Inspect what's wired up
llama stack list-providers
llama stack list-apis

# Model & shield management (when server is running)
llama-stack-client models list
llama-stack-client models register --model-id X --provider-id ollama --provider-model-id llama3.1:8b
llama-stack-client shields list
llama-stack-client shields register --shield-id content_safety --provider-id llama-guard

# Inspect the running server
llama-stack-client inspect health
llama-stack-client inspect version
llama-stack-client providers list

# OGX entrypoint (newer versions)
ogx stack run starter
ogx stack build --template starter
```

---

## Chapter 35. REST API Quick Reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness |
| `GET` | `/v1/version` | Server version |
| `GET` | `/v1/models` | List models |
| `POST` | `/v1/models` | Register model |
| `POST` | `/v1/inference/chat-completion` | Chat (legacy) |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat |
| `POST` | `/v1/embeddings` | Embeddings |
| `POST` | `/v1/responses` | Responses API (create) |
| `GET` | `/v1/responses/{id}` | Retrieve response |
| `DELETE` | `/v1/responses/{id}` | Delete response |
| `GET` | `/v1/shields` | List shields |
| `POST` | `/v1/shields` | Register shield |
| `POST` | `/v1/safety/run-shield` | Run a shield |
| `POST` | `/v1/moderations` | OpenAI moderations |
| `GET` | `/v1/vector-dbs` | List vector DBs |
| `POST` | `/v1/vector-dbs` | Register vector DB |
| `POST` | `/v1/vector-io/insert` | Insert vectors |
| `POST` | `/v1/vector-io/query` | Query vectors |
| `POST` | `/v1/vector-stores` | Create vector store (OpenAI-compatible) |
| `POST` | `/v1/vector-stores/{id}/files` | Add file to store |
| `POST` | `/v1/vector-stores/{id}/search` | Search store |
| `POST` | `/v1/files` | Upload file |
| `GET` | `/v1/files/{id}` | Retrieve file |
| `POST` | `/v1/toolgroups` | Register toolgroup (incl. MCP) |
| `GET` | `/v1/toolgroups` | List toolgroups |
| `POST` | `/v1/tool-runtime/rag-tool/insert` | RAG insert |
| `POST` | `/v1/tool-runtime/rag-tool/query` | RAG query |
| `POST` | `/v1/agents` | Create agent (legacy) |
| `POST` | `/v1/agents/{id}/sessions` | Create session (legacy) |
| `POST` | `/v1/agents/{id}/sessions/{sid}/turn` | Run turn (legacy) |
| `POST` | `/v1/scoring/score` | Run scoring |
| `POST` | `/v1/eval/run-eval` | Run evaluation |
| `POST` | `/v1/post-training/supervised-fine-tune` | SFT job |

---

## Chapter 36. Troubleshooting & Pitfalls

### Schema Mismatches

| Error | Cause | Fix |
|---|---|---|
| `ValidationError: storage` | Modern schema on FMS image | Use legacy `metadata_store:` |
| `ValidationError: metadata_store` | Legacy schema on 0.3.x image | Use `storage:` block |
| `vllm: extra_forbidden 'base_url'` | Used `base_url` on legacy schema | Use `url:` |

### Provider Not Found

| Error | Cause | Fix |
|---|---|---|
| `Provider 'remote::trusty_fms' is not available for API 'safety'` | Standard `rh-dev` image lacks the provider | Use FMS image; set `external_providers_dir` |
| `Failed to resolve 'tool_runtime' provider 'rag-runtime': required dependency 'vector_io' is not available` | Genaiops chart's namespace conditional dropped vector_io | Always include vector_io provider when RAG enabled |
| `remote::milvus: Field required (token)` | Missing `token` in milvus config | Set `token: root:Milvus` (default) |

### Operator/Distribution

| Error | Cause | Fix |
|---|---|---|
| Custom image ignored | Set both `distribution.name` and `distribution.image` | Set only `distribution.image` |
| `cannot import into current release` (helm) | Manually-created Route conflicts | `oc delete route <name>` then re-upgrade |

### Networking

| Error | Cause | Fix |
|---|---|---|
| File upload times out at 30s | OpenShift route default | Annotate `haproxy.router.openshift.io/timeout=300s` |
| `SSL: CERTIFICATE_VERIFY_FAILED` calling KServe | OpenShift service-CA not trusted | Mount service-ca configmap, append to bundle, set `SSL_CERT_FILE` |
| `Connection refused` to vLLM via Llama Stack | Llama Stack ServiceAccount lacks RBAC for kube-rbac-proxy in front of KServe | Grant SA the appropriate `inferenceservices/get` role |

### Vector Stores

| Error | Cause | Fix |
|---|---|---|
| `400 Bad Request: embedding_dimension` | Empty string passed | Omit field or send int |
| Genaiops chart drops vector_io in non-test/prod namespaces | Namespace-name conditional in template | Patch chart or use a namespace name containing "test"/"prod" |

### Inference

| Error | Cause | Fix |
|---|---|---|
| Model not found by Agent / chat | Model ID changed between distros | Re-list models, update ID; e.g. `vllm-llama32/llama32` vs `vllm/llama32` |
| `litellm: Connection error` proxying vLLM | TLS trust missing | Trust OpenShift service-ca in LiteLLM container |

### Shields

| Error | Cause | Fix |
|---|---|---|
| `language_detection` flags every request | Missing `allowed_languages` param — orchestrator treats any detection as a violation | Set `params: {allowed_languages: ["en"]}` |
| Shield latency >2s | Detector InferenceService cold-started | Set `minReplicas: 1` on detector |

### Helm / OpenShift Console

When charts need to install from the OpenShift web console without manual steps, ensure they are **fully self-contained**:
- All RBAC, SCCs, and ConfigMaps templated.
- No external init job that requires a kubeconfig outside the cluster.
- No hardcoded user identities (`kube:admin`); auto-detect or expose as values.

---

## Chapter 37. Glossary

| Term | Meaning |
|---|---|
| **API** | One of the named capabilities (inference, safety, responses, …) the server exposes |
| **Provider** | An implementation of an API — inline (in-process) or remote (HTTP adapter) |
| **Distribution / Distro** | A pre-bundled `run.yaml` for a target environment |
| **Resource** | A user-registered entity (model, shield, vector_db, toolgroup) tracked in a routing table |
| **Routing Table** | The internal registry mapping resource IDs to providers |
| **Router** | The dispatcher that picks the right provider for a request based on the resource ID |
| **Shield** | A safety check identified by `shield_id`, backed by a safety provider |
| **Toolgroup** | A named bundle of tools (e.g. `mcp::filesystem`, `builtin::websearch`) |
| **Agents API** | Legacy stateful conversation API (deprecated 0.3.0) |
| **Responses API** | Modern OpenAI-compatible stateful API (`previous_response_id`) |
| **MCP** | Model Context Protocol — a standard for tool servers, used over SSE in Llama Stack |
| **OGX** | Rebrand of Llama Stack (2026) — same APIs, new name |
| **FMS image** | Custom Llama Stack image (`quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms`) shipping the IBM Guardrails `remote::trusty_fms` provider |
| **rh-dev** | Default Red Hat OpenShift AI Llama Stack distribution name |
| **KServe** | Kubernetes ML model serving CRD — used to host vLLM and detector models |

---

## Appendix A — End-to-End Walkthrough: From Zero to a Production-Ready Tenant

This appendix puts every chapter together. The goal: stand up Llama Stack with vLLM, Milvus, Docling, Trusty FMS guardrails, OTEL telemetry, and serve a tenant with their own RAG corpus.

```bash
# 1. Cluster: install operators
oc apply -f https://raw.githubusercontent.com/llamastack/llama-stack-k8s-operator/main/release/operator.yaml
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install milvus hassanbadawy/milvus -n omni
helm install llama-stack hassanbadawy/llama-stack -n omni \
  --set guardrails.enabled=true \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.omni.svc:19530" \
  --set vllm.url="http://llama32-predictor.ai501.svc:8080/v1"

# 2. Telemetry: OTEL collector → Jaeger + Prometheus
oc apply -f telemetry/otel-collector.yaml -n omni

# 3. Annotate route
oc annotate route llama-stack haproxy.router.openshift.io/timeout=300s -n omni

# 4. Create tenant resources
ENDPOINT="https://llama-stack-omni.apps.$CLUSTER"
python <<'PY'
from llama_stack_client import LlamaStackClient
import requests
from io import BytesIO

c = LlamaStackClient(base_url="$ENDPOINT")

# Per-tenant vector DB
c.vector_dbs.register(
    vector_db_id="vec__acme",
    embedding_model="nomic-embed-text-v1.5",
    embedding_dimension=768,
    provider_id="milvus",
)

# Upload files (Docling will parse)
for url in TENANT_DOC_URLS:
    buf = BytesIO(requests.get(url).content)
    buf.name = url.rsplit("/",1)[-1]
    f = c.files.create(file=buf, purpose="assistants")
    c.vector_stores.files.create("vec__acme", file_id=f.id)

# Sanity check via Responses API
r = c.responses.create(
    model="vllm/llama32",
    input="Summarize our onboarding policy.",
    instructions="Cite sources from the company docs.",
    tools=[{"type": "file_search", "vector_store_ids": ["vec__acme"]}],
    extra_body={"guardrails": ["content_safety", "prompt_injection",
                               "language_detection", "regex"]},
)
print(r.output_text)
PY
```

You now have a multi-tenant, observable, guardrailed RAG platform on OpenShift, fully built on Llama Stack APIs. From here, every chapter in this handbook can extend it: add MCP tools (Ch. 24), add multi-agent orchestration (Ch. 30), add HPA + Postgres backends for scale (Ch. 29), add Grafana dashboards (Ch. 28), and tune RAG (Ch. 25).

— *End of Handbook* —


