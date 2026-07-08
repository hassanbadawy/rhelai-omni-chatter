# RAG and Vector Store

## Summary [coverage: high -- 5 sources]

The rhelai-omni-chatter RAG path moves user-uploaded files through a fixed pipeline before they become retrievable context for chat:

```
File upload → /v1/openai/v1/files (Streamlit uses ChatCompletions-compatible files API)
  → /v1/vector-stores/{id}/files (chunk: 512 tokens, overlap: 50)
  → embeddings (inline::sentence-transformers, e.g. granite-embedding-125m)
  → Milvus
```

At chat time, the UI calls `/v1/vector-stores/{id}/search`, prepends the returned chunks to the user prompt, then issues the chat completion. Embeddings are produced in-pod by `inline::sentence-transformers` (Llama Stack auto-registers `granite-embedding-125m`, 768-dim). The vector store itself runs as Milvus, in one of two modes selected by the `milvus.mode` value in `helm/llama-stack`:

- **`milvus.mode=inline`** — embedded Milvus backed by SQLite at `/opt/app-root/src/.llama/distributions/rh/milvus.db` inside the llama-stack pod. No external service needed, but **wiped on every pod restart** (no PVC behind the file).
- **`milvus.mode=remote`** — connects to a standalone Milvus deployed via `helm/milvus` at `http://milvus.<ns>.svc:19530`. Survives pod restarts; required for any RAG data that must persist.

The split is deliberate: inline is the zero-friction default for demos, remote is the production-correct mode. Llama Stack abstracts both behind the same `vector_io` provider API, so application code does not change between modes — only the helm values do.

## Architecture & Design [coverage: high -- 3 sources]

**Document upload (from [`architecture.md`](../../wiki/architecture.md)):**

```
File upload → /v1/openai/v1/files (Streamlit uses ChatCompletions-compatible files API)
  → /v1/vector-stores/{id}/files (chunk: 512 tokens, overlap: 50)
  → embeddings (inline::sentence-transformers, e.g. granite-embedding-125m)
  → Milvus
```

The Streamlit UI in `llama-stack-ui/pages/documents.py` drives this flow. Files are sent as multipart uploads to Llama Stack's OpenAI-compatible files endpoint (`/v1/openai/v1/files`), then attached to a vector store via `/v1/vector-stores/{id}/files`. Llama Stack chunks the content (default 512 tokens, 50 overlap), embeds each chunk with the registered embedding model, and writes vectors to the configured `vector_io` provider — Milvus in our deployment.

**Chat-time retrieval:** the chat path in `pages/chat.py` runs:

```
User input
  ├─► [shield: input_shields] /v1/safety/run-shield
  ├─► [RAG] /v1/vector-stores/{id}/search → prepend chunks to prompt
  ├─► /v1/responses (streaming, previous_response_id for history)
  └─► [shield: output_shields] /v1/safety/run-shield
```

RAG is one branch of the pre-LLM data flow, in parallel with the input shield call. The retrieved chunks are prepended to the user message before the chat completion request goes out.

**Provider abstraction.** Llama Stack registers a `vector_io` provider that fronts whatever vector backend is configured. In our chart it is either `inline::milvus` (embedded SQLite) or `remote::milvus` (talks to a real Milvus pod via gRPC :19530). The application API surface (`/v1/vector-stores/...`) is identical in both cases. The `rag-runtime` tool provider references the vector_io provider by id (`vectorio_provider: milvus`), which is how the dependency wiring is expressed in Llama Stack's config.

**Embedding service.** `inline::sentence-transformers` runs the embedding model in-process inside the llama-stack pod — no separate inference service, no additional pod. Llama Stack auto-registers the embedding model on startup; the LLM (vLLM) is the one that has to be declared explicitly via `vllm.modelId`.

## Decisions & Rationale [coverage: high -- 3 sources]

**Why two Milvus modes (from [`architecture.md`](../../wiki/architecture.md)):**

> `milvus.mode=inline` runs an embedded SQLite-backed Milvus inside the llama-stack pod. Lightweight, but loses all data on pod restart (no PVC behind the SQLite file).
>
> `milvus.mode=remote` connects to a standalone Milvus service. Survives restarts, supports proper scale-out. Required for any RAG data that must persist.

The split exists because demos and quick PoCs do not want to provision a second StatefulSet just to upload a couple of PDFs, while production RAG cannot accept silent data loss on pod restart. One value flag, one chart, two correct deployments.

**Why our chart uses a `milvus.mode` value rather than the genaiops namespace-based conditional.** The upstream `genaiops/llama-stack-operator-instance` chart has a template condition that only includes `remote::milvus` when the namespace contains `"test"` or `"prod"`:

```go
{{- if and .Values.rag.enabled (or (contains "test" .Release.Namespace) (contains "prod" .Release.Namespace)) }}
vector_io:
- provider_id: milvus
  provider_type: remote::milvus
{{- end }}
```

For namespaces like `user1-canopy`, `user2-canopy`, or any custom name, this gives `inline::milvus` even with `rag.enabled=true` — and worse, depending on chart version, the `vector_io` provider section may be missing entirely from the rendered config, while `rag-runtime` still references it. That manifests as the runtime error:

```
RuntimeError: Failed to resolve 'tool_runtime' provider 'rag-runtime':
required dependency 'vector_io' is not available
```

Our chart replaced the namespace-based gating with an explicit `milvus.mode` value (`inline` | `remote`). It works in any namespace, and the vector_io provider is always rendered when RAG is enabled. See [`architecture.md` "Why Milvus has two modes"](../../wiki/architecture.md) and [`pitfalls.md` #22](../../wiki/pitfalls.md).

**Why `granite-embedding-125m` (768-dim) as default.** It is auto-registered by `inline::sentence-transformers`, runs in-process (no extra pod), and the dimension is known and stable. The Settings page reads `embedding_dimension` from the model's metadata, but a manually-edited config or missing metadata can stick a wrong dimension into vector store creation — see Pitfalls below.

**Why server-side shields wrap the RAG response.** The same `/v1/safety/run-shield` call that runs on input also runs on the LLM output, regardless of whether the response was RAG-augmented. This means injected adversarial content inside a retrieved chunk that successfully prompts the LLM into emitting a violation is still caught on the output side. The decision to keep input AND output shields applies even when RAG is enabled — RAG context is treated as untrusted input from a safety perspective.

## Operational Notes [coverage: high -- 2 sources]

**Deploying remote Milvus (from [`runbook.md`](../../wiki/runbook.md)):**

```bash
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.<ns>.svc:19530" \
  --set milvus.token="root:Milvus"
```

The default token is `"root:Milvus"`. The `remote::milvus` provider requires the `token` field; missing it fails with `Field required` at startup (see Pitfalls).

**Verifying which Milvus mode is live:**

```bash
oc exec -n <ns> deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/providers \
  | jq '.[] | select(.api=="vector_io") | {provider_id, provider_type}'
```

If `provider_type` is `inline::milvus`, data is ephemeral. `remote::milvus` is the persistent mode.

**Route timeout for long uploads.** OpenShift routes default to a 30-second timeout. Embedding a large document during upload can exceed this, leaving the file half-ingested. Always annotate the route after deploy:

```bash
oc annotate route llama-stack -n $NS \
  haproxy.router.openshift.io/timeout=300s
```

The annotation key is `haproxy.router.openshift.io/timeout=300s`. Without it, the upload appears to hang from the UI's perspective; from the server's, the connection was closed mid-embedding.

**Vector store registration.** Vector stores are created via the standard Llama Stack `/v1/vector-stores` API. The UI creates them on demand from `pages/documents.py`. The required field that consistently bites people is `embedding_dimension`: it must be an integer (e.g. `768` for granite-embedding-125m). An empty string causes `400 Bad Request`.

**Verifying llama-stack came up correctly:**

```bash
# Models registered (must include the vllm/-prefixed LLM)
curl -s http://llama-stack-service:8321/v1/models | jq '.data[].id'

# Vector_io provider — check inline vs remote Milvus
curl -s http://llama-stack-service:8321/v1/providers \
  | jq '.[] | select(.api=="vector_io") | {provider_id, provider_type}'
```

## Pitfalls & Known Issues [coverage: high -- 2 sources]

**`remote::milvus` requires the `token` field.** Configuring remote Milvus without `milvus.token` fails on llama-stack startup with `Field required`. Default value: `"root:Milvus"`. Our chart sets this automatically; the genaiops chart also handles it. From [`components.md`](../../wiki/components.md):

> Standalone Milvus, optional. Default token `root:Milvus`. Required token field on `remote::milvus` provider; missing it fails with `Field required`.

**Genaiops chart namespace-based conditional skips `remote::milvus`.** The upstream genaiops chart only renders the `remote::milvus` provider when the namespace name contains `"test"` or `"prod"`. For any other namespace (`user1-canopy`, `agentic-ivr`, etc.), even `rag.enabled=true` produces `inline::milvus` — and in some chart versions, no `vector_io` provider at all.

**Missing `vector_io` provider when RAG is enabled but namespace doesn't match.** Direct consequence of the above. Even when the genaiops chart includes `vector_io` in the `apis` list and the `rag-runtime` references `vectorio_provider: milvus`, the actual `vector_io` provider section may be absent from `providers` due to the namespace conditional. Result:

```
RuntimeError: Failed to resolve 'tool_runtime' provider 'rag-runtime':
required dependency 'vector_io' is not available
```

Our chart fixes this by always rendering the vector_io provider when RAG is enabled, gated only on `milvus.mode`.

**Empty `embedding_dimension` causes `400 Bad Request`.** From [`pitfalls.md` #7](../../wiki/pitfalls.md):

> The embedding dimension must match the model's actual output dimension. The Settings page reads `embedding_dimension` from the model's metadata, but if the user edits `config.yaml` manually or the metadata is missing, the stored dimension may be wrong.

The `/v1/vector_stores` API requires `embedding_dimension` as an integer. An empty string (`""`) is rejected with `400 Bad Request`. The UI handles this by omitting the field when empty, but a manually edited `config.yaml` can still bypass that. Always select the embedding model via the Settings UI.

**Route timeout default 30s kills large uploads.** The OpenShift HAProxy ingress closes the connection after 30 seconds. Embedding even a moderately sized document can exceed this. Symptom: upload hangs in the UI, server logs show the connection dropped mid-embedding. Fix: annotate the route with `haproxy.router.openshift.io/timeout=300s` (see Operational Notes).

**Inline mode loses all data on pod restart.** From [`pitfalls.md` #22](../../wiki/pitfalls.md):

> The `helm/llama-stack` chart defaults to `milvus.mode: inline`, which configures an embedded Milvus backed by a SQLite file at `/opt/app-root/src/.llama/distributions/rh/milvus.db`. There is no PVC; the file lives on the pod's writable layer and is wiped on every restart.

Symptom: vector stores and uploaded documents disappear after a llama-stack pod restart, RAG queries return zero hits. Detection:

```bash
curl /v1/providers | jq '.[] | select(.api=="vector_io")'
```

If `provider_type` is `inline::milvus`, data is ephemeral. Switch to `milvus.mode=remote` for persistence.

**Helm `--reuse-values` carries forward stale Milvus endpoint.** Like `vllm.url`, the `milvus.endpoint` from a previous upgrade is reused literally. If the standalone Milvus pod is moved to a different namespace or its service name changes, the next `helm upgrade --reuse-values` keeps the dead endpoint and embeddings silently fail to write. Always re-source from cluster truth on every upgrade.

## Findings & Measurements [coverage: low -- 0 RAG-specific benchmarks]

**Gap.** No measured numbers exist in the wiki specifically for RAG retrieval — no top-K latency curves, no recall@K benchmarks against a labeled corpus, no inline-vs-remote Milvus throughput comparison. [`model-benchmarks.md`](../../wiki/model-benchmarks.md) measures LLM TTFT and throughput (qwen25-7b-instruct vs gpt-oss-20b) but treats RAG as out of scope.

What is documented qualitatively:

- **Use-case routing.** From [`components.md`](../../wiki/components.md): for long RAG answers, `vllm/gpt-oss-20b` is preferred over `vllm/qwen25-7b-instruct` because it has ~3x higher throughput (~98 tok/s vs ~30 tok/s) and the TTFT penalty (~500ms vs ~45ms) amortizes over a long response. This is an LLM property, not a vector-store property — Milvus retrieval latency was not measured separately.
- **Chunk sizing.** 512 tokens with 50-token overlap is the default; no a/b comparison against other sizings is recorded.
- **Embedding model.** Only `granite-embedding-125m` (768-dim) has been deployed. No comparison against alternatives (e.g. multilingual-e5, bge-large) is on file.

These are open measurement tasks. Tag this section as low-coverage until at least one labeled-retrieval benchmark exists for the deployed Milvus + granite-embedding-125m stack.

## Sources

- [architecture.md](../../wiki/architecture.md) — RAG flow / document upload section, "Why Milvus has two modes"
- [components.md](../../wiki/components.md) — `helm/milvus`, embedding model section
- [decisions.md](../../wiki/decisions.md) — RAG / vector_io provider rationale (chart structure decisions)
- [pitfalls.md](../../wiki/pitfalls.md) — #7 (`embedding_dimension` mismatch), #22 (inline Milvus is ephemeral), genaiops namespace bug, missing vector_io provider
- [runbook.md](../../wiki/runbook.md) — vector store ops, route timeout annotation `haproxy.router.openshift.io/timeout=300s`, verify-which-mode-is-live curl
- [model-benchmarks.md](../../wiki/model-benchmarks.md) — referenced for the RAG-favoring model choice (gpt-oss-20b for long answers)
