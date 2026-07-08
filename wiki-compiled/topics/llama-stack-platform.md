# Llama Stack Platform

## Summary [coverage: high -- 7 sources]

**Llama Stack is the orchestration layer of `rhelai-omni-chatter`.** It sits behind the UI on REST port `8321` and brokers every call out to vLLM (LLM inference), the Guardrails Orchestrator (safety shields), and Milvus (RAG vector store). The UI never talks to vLLM, the orchestrator, or Milvus directly — only Llama Stack does. This single seam is what lets the same UI run unchanged whether `guardrails.enabled=false` (RHOAI default `rh-dev` image with `inline::llama-guard`) or `guardrails.enabled=true` (custom `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` image with `remote::trusty_fms`).

In this project, Llama Stack is delivered as the [`helm/llama-stack`](../../wiki/components.md) chart, which deploys a `LlamaStackDistribution` CR (the operator then creates the Service as `llama-stack-service`, **not** `llama-stack`). It is consumed by [`helm/llama-stack-ui`](../../wiki/components.md) (our custom Streamlit app) and optionally by the upstream [`helm/llama-stack-playground`](../../wiki/components.md). Models served by vLLM must be explicitly registered via `vllm.modelId` and are then exposed under a `vllm/` prefix at `/v1/models` (e.g. `vllm/qwen25-7b-instruct`). Inference and safety travel two completely independent paths through the platform — the orchestrator never calls vLLM, vLLM never calls the orchestrator, and the UI is the only component that chains them.

## Architecture & Design [coverage: high -- 5 sources]

**Layered design.** Per [`architecture.md`](../../wiki/architecture.md), the deployed stack is layered with stable HTTP boundaries between every layer:

```
UI layer (helm/llama-stack-ui or helm/llama-stack-playground)
     │ HTTPS (OpenShift Route, edge TLS)
     ▼
Llama Stack (helm/llama-stack)  — REST API on :8321
     │
     ├─► HTTPS :8443  → vLLM (KServe InferenceService)
     ├─► HTTP  :8080  → Guardrails Orchestrator + bundled detectors
     └─► HTTP  :19530 → Milvus (standalone or inline)
```

**Two-image story.** The chart switches between two completely different images depending on `guardrails.enabled`:

| | `guardrails.enabled=false` | `guardrails.enabled=true` |
|--|---|---|
| Image | `rh-dev` (RHOAI operator default) | `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` |
| Safety provider | `inline::llama-guard` | `remote::trusty_fms` |
| Config schema | `metadata_store` + `storage.{backends,stores}` | `type: sqlite, db_path: ...` |
| `external_providers_dir` | not set | `/opt/app-root/src/.llama/providers.d/` |

The `remote::trusty_fms` provider is **not** in upstream Llama Stack — it lives only in the FMS image. The next-closest upstream candidate, `remote::passthrough`, calls `POST /moderations` (OpenAI moderation format), which is incompatible with the IBM/FMS Guardrails Orchestrator API (`POST /api/v1/text/contents`). See pitfall 14.

**Two independent paths.** The single most important architectural fact in [`architecture.md`](../../wiki/architecture.md): inference and safety never intersect inside Llama Stack.

```
Path 1 — LLM Inference:
  Client → Llama Stack (/v1/responses) → remote::vllm → vLLM → LLM model

Path 2 — Safety Checks:
  Client → Llama Stack (/v1/safety/run-shield) → remote::trusty_fms → orchestrator → detectors
```

The UI orchestrates both: it calls `/v1/safety/run-shield` on input, then `/v1/responses` (or `/v1/chat/completions`) for inference, then `/v1/safety/run-shield` on output. Llama Stack itself does not chain them automatically.

**Provider surface used by this project** (from [`components.md`](../../wiki/components.md), [`llama-stack-api-improvements.md`](../../wiki/llama-stack-api-improvements.md)):

- `remote::vllm` — LLM inference (vLLM behind kube-rbac-proxy, port 8443, self-signed TLS).
- `remote::trusty_fms` — safety, custom provider in the FMS image.
- `remote::milvus` (or `inline::milvus`) — RAG vector store, switched by `milvus.mode`.
- `inline::sentence-transformers` — embeddings, auto-registered (e.g. `granite-embedding-125m`, 768-dim).

**API endpoints actually consumed** (from [`llama-stack-api-improvements.md`](../../wiki/llama-stack-api-improvements.md)): `GET /v1/health`, `GET /v1/models`, `GET /v1/providers`, `GET /v1/shields`, `POST /v1/chat/completions`, `POST /v1/safety/run-shield`, `GET|POST|DELETE /v1/vector_stores[/{id}]`, `POST /v1/files`, `POST /v1/vector_stores/{id}/files`, `POST /v1/vector_stores/{id}/search`. Defined-but-unused endpoints (Responses API, Conversations API, embeddings, batch ingestion, prompt templates, `/v1alpha/*` admin and rerank) are still latent in `modules/api.py` for future enablement.

## Decisions & Rationale [coverage: high -- 8 decisions in decisions.md]

Verbatim "why" lines pulled from [`decisions.md`](../../wiki/decisions.md):

1. **Chat Completions API instead of Responses API.** "The Responses API does not forward `max_tokens` to the underlying vLLM backend. The server injects its own `VLLM_MAX_TOKENS` default (e.g. 4096) regardless of what the client sends." Chat Completions passes `max_tokens` through correctly. The Responses API methods remain in `modules/api.py` as dead code in case the vLLM forwarding issue is fixed upstream.

2. **Client-side conversation history.** Follows directly from the previous decision — Chat Completions is stateless, so the full message history must be sent with every request anyway. The Llama Stack Conversations API was not tested against the available `rh-dev` distribution. Trade-off: messages are lost on page refresh; `conversations.json` only persists names.

3. **Context length probing via `max_tokens=999999`.** The `/v1/models` metadata for vLLM-backed models frequently omits all context length fields (`max_seq_len`, `context_length`, `max_model_len`, `context_window` are all observed across server versions). The probe sends a real request and parses the descriptive vLLM error ("maximum context length is N tokens").

4. **Raw `requests` instead of the `llama-stack-client` SDK.** "The `llama-stack-client` Python SDK version must match the server version exactly, and the server version is controlled by the RHOAI operator." Using raw HTTP avoids version lock-in.

5. **UUID for conversation IDs.** After switching off the Responses API, there is no server-assigned ID; UUID is stable and independent of server state.

6. **`max_tokens` capped at `context_length / 2`.** "Reserving half the context for input … and half for output is a safe default. Without this cap, small-context models like `qwen25-vl-7b-instruct` (2024 tokens) will error on every request."

7. **Ship our own UI chart instead of relying on `llama-stack-playground`.** Genaiops `0.3.0-fix` has a `RAGDocument` dict-vs-object bug in `upload.py:59`, only invokes shields in Agent mode (Direct mode bypasses shields), and silently truncates SSE error frames inside HTTP 200 streams. Our UI fixes all three.

8. **`LLAMA_STACK_UI_DATA_DIR` redirects writable state away from the read-only image.** The Containerfile bakes a developer's `config.yaml` into the image. Without redirection, the stale `endpoint` value in that YAML overrides helm-supplied `LLAMA_STACK_API_ENDPOINT` because `load_config()` reads YAML first. The chart sets `LLAMA_STACK_UI_DATA_DIR=/tmp/llama-stack-ui-data` to bypass the baked YAML.

**Implicit "why" on the Llama Stack image choice.** The custom FMS image is the only way to get `remote::trusty_fms`, which is the only Llama Stack safety provider that natively speaks the IBM/FMS detector API (`/api/v1/text/contents`). All upstream providers (`inline::llama-guard`, `inline::prompt-guard`, `inline::code-scanner`, `remote::passthrough`, `remote::bedrock`, `remote::nvidia`) speak the wrong APIs (Llama Guard model, transformers, codeshield lib, OpenAI moderations, AWS Bedrock, NVIDIA NIM respectively). See [`architecture.md`](../../wiki/architecture.md) "Why a custom Llama Stack image when guardrails are on".

## Operational Notes [coverage: high -- runbook + components + handbook]

All recipes copy-pasteable from [`runbook.md`](../../wiki/runbook.md). Internal-cluster URLs only.

**Deploy with guardrails** (always re-source `vllm.url`, `vllm.apiToken`, `vllm.modelId` — `--reuse-values` is a footgun, see pitfall 24):

```bash
NS=user1-canopy
ISVC=qwen25-7b-instruct
TOKEN=$(oc get secret -n $NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d)
VLLM_URL="https://${ISVC}-predictor.${NS}.svc.cluster.local:8443/v1"

helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set guardrails.enabled=true \
  --set guardrails.hap.enabled=true \
  --set guardrails.hap.confidence_threshold=0.5 \
  --set guardrails.prompt_injection.enabled=true \
  --set guardrails.prompt_injection.confidence_threshold=0.5 \
  --set guardrails.language_detection.enabled=true \
  --set guardrails.language_detection.confidence_threshold=0.99 \
  --set guardrails.regex.enabled=true \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.${NS}.svc:19530" \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

**Deploy without guardrails:**

```bash
helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

**Verification curls** (must run from inside the cluster — `llama-stack-service` is not external):

```bash
# Models registered (must include the vllm/-prefixed LLM)
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/models | jq '.data[].id'

# Vector_io provider — check inline vs remote Milvus
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/providers \
  | jq '.[] | select(.api=="vector_io") | {provider_id, provider_type}'

# Shields registered
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/shields | jq '.data[].identifier'
```

**TLS verify on vLLM provider.** Both config blocks (guardrails-on and guardrails-off) must render `tls_verify: false`. OpenShift InferenceServices terminate TLS at kube-rbac-proxy with a self-signed serving cert; without `tls_verify: false` every chat completion fails with `APIConnectionError 500` even though `curl -k` from the same pod works. Verify the rendered configmap:

```bash
oc get cm llama-stack-config -n $NS -o jsonpath='{.data.config\.yaml}' | grep -A3 'provider_id: vllm'
# Should show three keys: url, api_token, tls_verify
```

**Helm upgrade caveat.** `--reuse-values` carries forward whatever was previously set, including `vllm.url`, `vllm.apiToken`, `vllm.modelId`. When the running InferenceService is swapped or its SA token rotated, those reused values go stale and cause `APIConnectionError` (DNS) or `404 model not found`. Always re-source:

```bash
TOKEN=$(oc get secret -n <ns> default-token-<isvc>-sa -o jsonpath='{.data.token}' | base64 -d)
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set vllm.url="https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="<isvc>"
```

**Route timeout for long uploads.** OpenShift routes default to 30s; embedding a large document during file upload can exceed it:

```bash
oc annotate route llama-stack -n $NS haproxy.router.openshift.io/timeout=300s
```

**Helm repo.** Charts published at `https://hassanbadawy.github.io/rhelai-omni-chatter/` (packages as GitHub Releases, `index.yaml` on `gh-pages`):

```bash
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install llama-stack hassanbadawy/llama-stack
```

## Pitfalls & Known Issues [coverage: high -- 12+ relevant pitfalls]

All entries from [`pitfalls.md`](../../wiki/pitfalls.md). Numbers are the original pitfalls.md indices.

- **#16 — `vllm.modelId` required, model auto-prefixed with `vllm/`.** Llama Stack auto-registers the embedding model from `inline::sentence-transformers` but **not** the served LLM. Without `vllm.modelId`, `/v1/models` only shows embeddings and chat completions return `400 Bad Request: model field expected string`. After registration, the LLM is exposed with a `vllm/` prefix — UIs must use the prefixed ID.

- **#17 — `tls_verify` missing in guardrails-mode vLLM provider config.** Both config blocks (rh-dev and FMS) need `tls_verify: false`. Missing it causes generic `APIConnectionError: Connection error` 500 — easy to misdiagnose as a routing problem because raw `curl -k` from the pod works fine.

- **#18 — Operator-managed Service is `llama-stack-service`, not `llama-stack`.** The `LlamaStackDistribution` CR is consumed by the `llama-stack-k8s-operator`, which generates the Service with a `-service` suffix. Both `helm/llama-stack-playground/values.yaml` and `helm/llama-stack-ui/values.yaml` default `llamaStackUrl` to `http://llama-stack-service:8321`.

- **#1 — Responses API silently ignores `max_tokens`.** `/v1/responses` does not forward `max_output_tokens` to vLLM; the adapter uses its own `VLLM_MAX_TOKENS` env var set at server startup. We switched to `/v1/chat/completions`. Detection: set `max_tokens=10` and verify the response is actually short.

- **#3 — Small-context models overflow on first message.** Default `max_tokens=2000` against `qwen25-vl-7b-instruct` (2024 tokens) errors on every request. Fix: `get_model_context_length()` probes the limit and we cap `effective_max_tokens = context_length // 2`.

- **#4 — SSE errors arrive inside HTTP 200 streams.** Llama Stack encodes errors as `{"error": {"message": "..."}}` in SSE `data:` lines while keeping the outer HTTP 200. `chat_completions_stream()` now explicitly checks for the `"error"` key and raises.

- **#5 — Model context length not in metadata.** Field name varies across server versions (`max_seq_len`, `context_length`, `max_model_len`, `context_window`). The method checks all four and falls back to a probe.

- **#8 — `vllm.api_token: fake` causes `Unauthorized`.** OpenShift vLLM InferenceServices use SA token auth; the helm default `fake` is rejected. Pull the SA token: `oc get secret -n <ns> default-token-<isvc>-sa -o jsonpath='{.data.token}' | base64 -d`. Must match the **same** InferenceService — using whisper SA against qwen predictor RBAC-fails (#13).

- **#14 — `remote::passthrough` is incompatible with IBM/FMS detectors.** `remote::passthrough` calls `POST /moderations` (OpenAI format); FMS exposes `POST /api/v2/text/detection/content`. Use `remote::trusty_fms` from the custom FMS image.

- **#22 — Inline Milvus stores RAG data ephemerally.** `milvus.mode: inline` defaults to a SQLite file at `/opt/app-root/src/.llama/distributions/rh/milvus.db` on the pod's writable layer with no PVC. Wiped on every restart. Switch to `milvus.mode=remote` for persistence.

- **#24 — `helm upgrade --reuse-values` carries forward stale values.** After an InferenceService swap, the reused `vllm.url`/`vllm.apiToken`/`vllm.modelId` go stale → `APIConnectionError` or `404 model not found`. Always re-source from cluster on every upgrade.

- **Two config schemas between the two images.** The `rh-dev` image uses `metadata_store` + `storage.backends`/`storage.stores` and `base_url` for the vLLM key; the FMS image uses `type: sqlite, db_path: ...` and `url` for the vLLM key. Mixing schemas across images causes pydantic `ValidationError`. The chart's `guardrails.enabled` conditional renders two completely separate config blocks. See [`pitfalls.md`](../../wiki/pitfalls.md) "Llama Stack Config Format" and the project [CLAUDE.md](../../CLAUDE.md).

- **#19 — Genaiops playground 0.3.0-fix file upload crashes** with `AttributeError: 'dict' object has no attribute 'content'` at `upload.py:59`. Read-only third-party image; mitigation is to use `helm/llama-stack-ui` instead.

## Findings & Measurements [coverage: high -- multiple dated entries]

Reverse-chronological. From [`findings.md`](../../wiki/findings.md) and dated pitfalls. Nothing in the wiki is yet old enough (>18 months) to flag stale.

- **2026-05-09 — LiteLLM TLS chain works end-to-end (claude-mem #813).** Full `llama-stack → LiteLLM → vLLM/KServe` chain verified working on the `agentic-ivr` cluster after fixing TLS trust on LiteLLM. Fix: `initContainer` combines OpenShift service-CA bundle with system CA bundle into one PEM mounted at `/etc/ssl/certs/ca-bundle.crt`; set `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE` to that path. Without this, LiteLLM rejected the vLLM KServe predictor's self-signed cert and llama-stack saw `500 Connection error`. Direct `llama-stack → vLLM` already worked because llama-stack had `tls_verify: false`. Commit: `3770ba6`.

- **2026-05-09 — Guardrails red-team: `language_detection` always trips on English greetings.** `papluca/xlm-roberta-base-language-detection` classifies short English greetings (`hi`, `hey, how are you`) as non-English at >0.9 confidence. With `confidence_threshold: 0.85`, every greeting is blocked. Mitigations: drop the shield, raise threshold to ≥0.99, or skip client-side for messages under N tokens. The model is fine on full sentences — issue is short-utterance ambiguity. See [`guardrails-redteam-report.md`](../../wiki/guardrails-redteam-report.md).

- **2026-05-09 — Fictional/hypothetical framing is the only full-stack guardrails bypass.** 11-attack adversarial suite against HAP, prompt_injection, language_detection, regex. Only the "fictional emergency" framing (e.g. *"In a story I'm writing, a character needs to ..."*) bypassed all four shields AND elicited the protected response from the LLM. Mitigations are model-side (tighter system prompt, refuse-to-roleplay clauses, output classifier on the response), not shield-side.

- **2026-05-09 — Wiki bootstrap.** Legacy `llama-stack-ui/docs/` and `docs/` were merged into `wiki/`. Pre-existing dated observations live in [`pitfalls.md`](../../wiki/pitfalls.md), [`decisions.md`](../../wiki/decisions.md), [`model-benchmarks.md`](../../wiki/model-benchmarks.md).

- **2026-05-09 — Model selection by use case** (from [`model-benchmarks.md`](../../wiki/model-benchmarks.md), summarized in [CLAUDE.md](../../CLAUDE.md)). Voice agent / plain streaming chat / multilingual: `qwen25-7b-instruct` (TTFT to user-visible content ~45 ms vs ~500 ms for gpt-oss; multilingual coverage stronger). Long RAG / agent flows: `gpt-oss-20b` (~98 vs ~30 tok/s; hidden chain-of-thought helps tool selection). Reasoning models stream `delta.reasoning_content` (and legacy `delta.reasoning`) — UIs that only read `delta.content` look frozen until reasoning ends.

- **Dated platform pitfalls** (also 2026-era, from [`pitfalls.md`](../../wiki/pitfalls.md)). Gemma 3n on RHOAI-shipped vLLM (`0.13.0+rhai11`, `0.11.2+rhai5`) generates `completion_tokens > 0` but `content: ""` — the `Gemma3nForConditionalGeneration` hybrid attention/SSM text decoder is not wired up; stay on `ForCausalLM`. Qwen3 emits `<think>...</think>` reasoning trace that consumes `max_tokens`; `extra_body.chat_template_kwargs.enable_thinking=false` is silently dropped by Llama Stack; reliable fixes are vLLM `--reasoning-parser qwen3`, UI strip, or switch to `qwen25-7b-instruct`.

## Sources

- [architecture.md](../../wiki/architecture.md)
- [components.md](../../wiki/components.md)
- [decisions.md](../../wiki/decisions.md)
- [llama-stack-api-improvements.md](../../wiki/llama-stack-api-improvements.md)
- [pitfalls.md](../../wiki/pitfalls.md)
- [runbook.md](../../wiki/runbook.md)
- [findings.md](../../wiki/findings.md)
- [handbooks/llamastack-handbook.md](../../wiki/handbooks/llamastack-handbook.md)
