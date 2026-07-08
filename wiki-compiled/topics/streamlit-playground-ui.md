# Streamlit Playground UI

## Summary [coverage: high -- 5 sources]

The Streamlit playground UI in [`llama-stack-ui/`](../../llama-stack-ui) is the primary user-facing surface for the rhelai-omni-chatter stack. It exposes three pages — chat (with streaming, RAG, and shields), document/RAG management, and settings — and orchestrates two server-side paths through Llama Stack: `POST /v1/chat/completions` for inference and `POST /v1/safety/run-shield` for safety. Both paths are independent inside Llama Stack, but the UI chains them per turn (input shield → RAG retrieval → chat completion → output shield). See [`architecture.md`](../../wiki/architecture.md) for the layered diagram.

The repository ships **two** UI helm charts and the custom one is the recommended path:

- [`helm/llama-stack-playground`](../../helm/llama-stack-playground) — packages the upstream `quay.io/rhoai-genaiops/llama-stack-playground:0.3.0-fix` image. Has two blocking bugs documented in [`architecture.md`](../../wiki/architecture.md) "Why a custom UI": (1) file upload crashes with `AttributeError: 'dict' object has no attribute 'content'` at `upload.py:59` because `RAGDocument` returns a `dict` in `llama-stack-client` 0.3.0; (2) the default chat mode is **Direct**, which bypasses safety shields entirely (shields only fire in Agent-based mode).
- [`helm/llama-stack-ui`](../../helm/llama-stack-ui) — packages our custom Streamlit app from [`llama-stack-ui/`](../../llama-stack-ui). Fixes the `RAGDocument` dict access, runs `/v1/safety/run-shield` on every message regardless of mode, adds context-length probing, and detects SSE errors that arrive inside HTTP 200 streams. See [`decisions.md`](../../wiki/decisions.md) decision 7 for the trade-off (we lose the upstream Agent/ReAct features in exchange).

## Architecture & Design [coverage: high -- 4 sources]

**Page structure** (per [`components.md`](../../wiki/components.md) and [`entanglements.md`](../../wiki/entanglements.md)):

- `app.py` — Streamlit entry point; page navigation only.
- `pages/chat.py` — chat with streaming via `POST /v1/chat/completions`, optional RAG via `POST /v1/vector_stores/{id}/search`, server-side shields via `POST /v1/safety/run-shield`. Owns the `conversations`, `active_chat_key`, `pending_chat_name`, and `_ctx_len_{model_id}` session-state keys.
- `pages/documents.py` — vector store CRUD via `GET/POST/DELETE /v1/vector_stores`, file upload via `POST /v1/files` then `POST /v1/vector_stores/{id}/files` (chunk: 512 tokens, overlap: 50). Reads `embedding_model`, `embedding_dimension`, and `vector_io_provider` from config.
- `pages/settings.py` — endpoint, model selectbox (from `GET /v1/models`), embedding model, vector_io provider, safety shields multiselect (from `GET /v1/shields`), sampling parameters, language, system prompt, `user_id`. Owns the `settings_model`, `settings_embedding`, `settings_vio` widget keys.

**`modules/api.py` is the only Llama Stack contract.** Per [`decisions.md`](../../wiki/decisions.md) decision 4, it uses raw `requests` instead of the `llama-stack-client` SDK to avoid version-locking against the RHOAI-operator-controlled server. The `LlamaStackClient` class wraps every endpoint listed in [`llama-stack-api-improvements.md`](../../wiki/llama-stack-api-improvements.md) "Current Coverage" — 13 endpoints currently consumed: `GET /v1/health`, `GET /v1/models`, `GET /v1/providers`, `POST /v1/chat/completions`, `GET/POST/DELETE /v1/vector_stores`, `POST /v1/vector_stores/{id}/{search,files}`, `GET /v1/vector_stores/{id}/files`, `POST /v1/files`, plus the safety methods (`run_shield()`, `get_shields()`, `get_shields_from()`, `register_shield()`, `get_safety_providers()`).

**`modules/config.py` is the YAML loader.** Reads `config.yaml` and writes `conversations.json` under `${LLAMA_STACK_UI_DATA_DIR}` if set, defaulting to the package directory. Empty-string YAML values are treated as "not set" so env-var defaults (`LLAMA_STACK_API_ENDPOINT`, `DEFAULT_MODEL`) take precedence. Every API call re-reads config via `load_config()` — there is no client-level cache (see [`entanglements.md`](../../wiki/entanglements.md) "config.yaml Field Consumers").

**Helm-managed env vars** (per [`components.md`](../../wiki/components.md) "helm/llama-stack-ui"):

| Helm value | Env var | Default |
|---|---|---|
| `ui.llamaStackUrl` | `LLAMA_STACK_API_ENDPOINT` | `http://llama-stack-service:8321` |
| `ui.defaultModel` | `DEFAULT_MODEL` | `""` (must include `vllm/` prefix) |
| (chart-set) | `LLAMA_STACK_UI_DATA_DIR` | `/tmp/llama-stack-ui-data` |

**Containerfile build** uses an OpenShift binary build, then the chart references the in-cluster registry image at `image-registry.openshift-image-registry.svc:5000/<namespace>/llama-stack-ui` by default. Override `image.repository` for an external registry. Route is created by default with edge TLS termination.

## Decisions & Rationale [coverage: high -- 2 sources]

**1. Chat Completions API instead of Responses API.** Per [`decisions.md`](../../wiki/decisions.md) decision 1 and [`pitfalls.md`](../../wiki/pitfalls.md) #1: the Responses API does not forward `max_tokens` to the underlying vLLM backend — the server injects its own `VLLM_MAX_TOKENS` default (e.g. 4096) regardless of what the client sends. This makes it impossible to control output length or prevent context overflow on small-context models. Chat Completions passes `max_tokens` through correctly. The Responses API methods (`create_response`, `_create_response_stream`, `list_responses`, `get_response`, `get_response_input_items`, `delete_response`) remain in `api.py` as **dead code**, kept in case the upstream vLLM forwarding issue is fixed (see [`entanglements.md`](../../wiki/entanglements.md) "Dead Code in api.py").

**2. Client-side conversation history (session state).** Per [`decisions.md`](../../wiki/decisions.md) decision 2: messages live in `st.session_state.conversations[conv_id]` keyed by UUID. Direct consequence of decision 1 — Chat Completions is stateless, so the full message history is sent per request anyway. The Llama Stack Conversations API was not tested against `rh-dev`. Known limitation: messages are lost on page refresh; `conversations.json` only persists conversation **names**, not message content (see [`entanglements.md`](../../wiki/entanglements.md) "conversations.json Structure").

**3. Context-length probing.** Per [`decisions.md`](../../wiki/decisions.md) decision 3 and [`pitfalls.md`](../../wiki/pitfalls.md) #5: `get_model_context_length()` in `api.py` first inspects metadata fields (`max_seq_len`, `context_length`, `max_model_len`, `context_window`) — the field name varies across server versions and is often missing entirely. It falls back to a request with `max_tokens=999999` and parses the vLLM error message ("maximum context length is N tokens"). The result is cached in `st.session_state[f"_ctx_len_{model_id}"]`. Per [`decisions.md`](../../wiki/decisions.md) decision 6, `effective_max_tokens = min(configured_max_tokens, context_length // 2)` — half the window reserved for input, half for output. This prevents `qwen25-vl-7b-instruct` (2024-token context) from erroring on every request. The contract with `chat.py` is documented in [`entanglements.md`](../../wiki/entanglements.md) "api.py → chat.py Context Length Contract" — three downstream behaviors (effective_max_tokens cap, message trimming, RAG context truncation) all read the cached value.

**4. Server-side shield delegation.** The UI never talks to detectors directly — every safety check goes through Llama Stack's `/v1/safety/run-shield`, which delegates to `remote::trusty_fms` and onward to the orchestrator. The dead-code methods `guardrails_chat()`, `check_external_detector()`, `run_external_detectors()`, `run_regex_filters()` exist in `api.py` for a hypothetical bypass path but are not wired (see [`entanglements.md`](../../wiki/entanglements.md) "Dead Code in api.py"). Active shield methods are `run_shield()`, `get_shields()`, `get_shields_from()`, `register_shield()`, `get_safety_providers()`.

**5. UUID for conversation IDs.** Per [`decisions.md`](../../wiki/decisions.md) decision 5: `str(uuid.uuid4())` instead of the previous server-assigned response ID (which tied identity to an ephemeral server object — broken once Chat Completions replaced Responses).

**6. `LLAMA_STACK_UI_DATA_DIR` indirection.** Per [`decisions.md`](../../wiki/decisions.md) decision 8: the Containerfile bakes a developer's `config.yaml` into `/opt/app-root/src/config.yaml`. Without indirection, that YAML's stale `endpoint` shadows the helm-supplied `LLAMA_STACK_API_ENDPOINT` because `load_config()` reads YAML first; and the OpenShift container is read-only at the image layer so the Settings page can't write back. The chart sets `LLAMA_STACK_UI_DATA_DIR=/tmp/llama-stack-ui-data` so the loader sees no YAML on first launch, falls back to env-var defaults, and persists Settings edits to a writable path.

## Operational Notes [coverage: high -- 2 sources]

**Build the image** via OpenShift binary build (per the project root `CLAUDE.md` build recipe — repeated here because [`components.md`](../../wiki/components.md) refers to [`runbook.md`](../../wiki/runbook.md) for the process):

```bash
oc new-build --binary --strategy=docker --name=llama-stack-ui -n <namespace>
oc patch bc/llama-stack-ui -n <namespace> --type=json \
  -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]'
oc start-build llama-stack-ui --from-dir=./llama-stack-ui --follow -n <namespace>
```

This populates `image-registry.openshift-image-registry.svc:5000/<namespace>/llama-stack-ui`. To use an external registry, override `image.repository`.

**Helm install** (per [`components.md`](../../wiki/components.md)):

```bash
helm install llama-stack-ui helm/llama-stack-ui/ -n <namespace> \
  --set ui.llamaStackUrl="http://llama-stack-service:8321" \
  --set ui.defaultModel="vllm/qwen25-7b-instruct"
```

The default backend URL is `http://llama-stack-service:8321` (operator-created service name — see [`pitfalls.md`](../../wiki/pitfalls.md) #18; the service is `llama-stack-service`, not `llama-stack`, because the `LlamaStackDistribution` operator generates the service name with the `-service` suffix). `ui.defaultModel` **must** include the `vllm/` prefix, since Llama Stack registers vLLM-served LLMs with that prefix.

**The `LLAMA_STACK_UI_DATA_DIR` trick.** The chart sets this to `/tmp/llama-stack-ui-data` automatically — do not set it to a path that doesn't exist or is read-only. To verify the env-var path is taking effect, exec into the pod and run:

```bash
python3 -c "from modules.config import load_config; print(load_config())"
```

If `endpoint` shows the developer URL instead of the chart-supplied one, the baked YAML is shadowing env vars — see [`pitfalls.md`](../../wiki/pitfalls.md) #15.

**Run locally** (per project root `CLAUDE.md`):

```bash
cd llama-stack-ui
export LLAMA_STACK_API_ENDPOINT="https://llama-stack-<namespace>.apps.<cluster>"
streamlit run app.py
# or: ./run.sh
```

`config.yaml` in the package dir is read first; the env var is the fallback when YAML is missing or empty.

## Pitfalls & Known Issues [coverage: high -- 2 sources]

- **Empty `embedding_dimension` → 400 Bad Request.** Per [`pitfalls.md`](../../wiki/pitfalls.md) #7 and the project root `CLAUDE.md`: `POST /v1/vector_stores` requires `embedding_dimension` as an integer. An empty string fails. The Settings page derives the dimension from live model metadata; never hand-edit this field in `config.yaml`.
- **Streamlit selectbox crash after endpoint change** ([`pitfalls.md`](../../wiki/pitfalls.md) #2). `st.selectbox` with an explicit `key` caches the last selection. Switching endpoints can leave a cached value that no longer exists in the new options list, raising `StreamlitAPIException` or returning a stale value silently. Fix: before each selectbox, delete the cached key if it isn't in the current options. Applied to `settings_model`, `settings_embedding`, `settings_vio` in `pages/settings.py`.
- **Model rename across charts** ([`pitfalls.md`](../../wiki/pitfalls.md) #16 and project root `CLAUDE.md`). The genaiops chart names vLLM providers `vllm-<model>` (e.g. `vllm-llama32/llama32`); our chart uses `vllm` (e.g. `vllm/llama32`). After switching charts, users must re-select the model in Settings — a stale `vllm-foo/foo` value will fail the `/v1/models` membership check.
- **Empty model dropdown.** Per [`pitfalls.md`](../../wiki/pitfalls.md) #16: `/v1/models` only lists embedding models if `vllm.modelId` is unset on the chart. Chat with `model=null` returns `400 Bad Request: {"loc":["body","model"], "msg":"Input should be a valid string"}`. Fix is in the chart (always set `vllm.modelId`); the UI surfaces it as an empty dropdown.
- **Helm-baked `config.yaml` shadows env vars** ([`pitfalls.md`](../../wiki/pitfalls.md) #15). The Containerfile copies a developer's `config.yaml` into the image. Without `LLAMA_STACK_UI_DATA_DIR` redirection, the baked YAML's `endpoint` overrides `LLAMA_STACK_API_ENDPOINT`. Both fixes are required: (1) treat empty-string YAML values as "not set", (2) point `LLAMA_STACK_UI_DATA_DIR` at a fresh writable dir.
- **Route timeouts on file uploads.** Per project root `CLAUDE.md`: OpenShift routes default to 30 seconds; embedding-time can exceed this for larger files. Annotate the route:
  ```bash
  oc annotate route llama-stack haproxy.router.openshift.io/timeout=300s
  ```
- **SSE errors inside HTTP 200 streams** ([`pitfalls.md`](../../wiki/pitfalls.md) #4). Llama Stack can encode errors as `{"error": {"message": "..."}}` inside an SSE `data:` line while still returning HTTP 200. The original code swallowed these via broad `KeyError`/`IndexError` catches. `chat_completions_stream()` now explicitly checks for the `"error"` key and raises `RuntimeError`; `_create_response_stream()` (dead code) handles the `response.failed` event the same way.
- **Dead Responses-API code in `api.py`.** Per [`entanglements.md`](../../wiki/entanglements.md) "Dead Code in api.py": `create_response()`, `_create_response_stream()`, `list_responses()`, `get_response()`, `get_response_input_items()`, `delete_response()`, `version()`, `guardrails_chat()`, `check_external_detector()`, `run_external_detectors()`, `run_regex_filters()` are all unused. The Responses-API ones are kept intentionally per [`decisions.md`](../../wiki/decisions.md) decision 1; the others are speculative paths that were never wired.
- **Manual `oc create route` conflicts with helm upgrade.** Per project root `CLAUDE.md`: `helm upgrade` will fail with "cannot import into current release" if you manually created a route. Delete it first: `oc delete route llama-stack -n <namespace>`.
- **Inline Milvus loses RAG data on pod restart** ([`pitfalls.md`](../../wiki/pitfalls.md) #22). The chart defaults to `milvus.mode: inline` (embedded SQLite at `/opt/app-root/src/.llama/distributions/rh/milvus.db`, no PVC). Vector stores and uploaded documents are wiped on restart. Switch to `milvus.mode=remote` for persistence.
- **`language_detection` shield blocks short greetings** ([`pitfalls.md`](../../wiki/pitfalls.md) #23). The detector model `papluca/xlm-roberta-base-language-detection` mis-classifies `hi` and `hey, how are you` as non-English at 0.91–0.98 confidence. Genaiops "worked" because Direct mode skips shields entirely, and Agent mode wraps the message in a long preamble. Our UI calls `run-shield` on the raw message — fix options: drop the shield, raise threshold to ≥0.99, add min-length skip in `chat.py`, or output-only.

## Findings & Measurements [coverage: medium -- 2 sources]

This topic carries no latency or throughput numbers — those live in [`model-benchmarks.md`](../../wiki/model-benchmarks.md). The dated observations relevant to the UI are upstream-bug findings that drove our fork:

- Genaiops `llama-stack-playground:0.3.0-fix` file upload crashes at `/app/llama_stack/distribution/ui/page/upload/upload.py:59` with `AttributeError: 'dict' object has no attribute 'content'` because `RAGDocument` is a `dict` in `llama-stack-client` 0.3.0. Documented in [`pitfalls.md`](../../wiki/pitfalls.md) #19. Three remediation options were considered (use our UI; build a patched genaiops image; mount a patched `upload.py` via ConfigMap) — option 1 was chosen, see [`decisions.md`](../../wiki/decisions.md) decision 7.
- Genaiops default chat mode is **Direct**, which calls the LLM with no shield wrapping. Shields only fire in Agent-based mode, and even there, the agent runtime wraps the user message in a longer preamble before the safety call. Our UI calls `/v1/safety/run-shield` directly on the raw message in every mode — documented in [`pitfalls.md`](../../wiki/pitfalls.md) #23 (the `language_detection` short-greeting issue is a side effect of this stricter wrapping).
- Streamlit selectbox stale-state bug ([`pitfalls.md`](../../wiki/pitfalls.md) #2) — observed during endpoint switching in the Settings page; fix applied in `pages/settings.py`.
- vLLM context-length metadata is inconsistent across server versions ([`pitfalls.md`](../../wiki/pitfalls.md) #5). The probe path in `get_model_context_length()` exists because of this.

[`llama-stack-api-improvements.md`](../../wiki/llama-stack-api-improvements.md) catalogs the 13 currently-consumed endpoints and the high-priority improvements that would expand coverage (Conversations API for persistent history, Responses API for agentic flows, batch file ingestion, prompt templates, reranking).

## Sources

- [architecture.md](../../wiki/architecture.md)
- [components.md](../../wiki/components.md)
- [decisions.md](../../wiki/decisions.md)
- [entanglements.md](../../wiki/entanglements.md)
- [pitfalls.md](../../wiki/pitfalls.md)
- [llama-stack-api-improvements.md](../../wiki/llama-stack-api-improvements.md)
