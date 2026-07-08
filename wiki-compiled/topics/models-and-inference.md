# Models and Inference

## Summary [coverage: high -- 5 sources]

This stack runs LLMs on KServe `InferenceService` instances (vLLM behind kube-rbac-proxy on `:8443`) and exposes them through Llama Stack with a `vllm/` prefix. The two production-suitable models are:

- **`vllm/qwen25-7b-instruct`** — the default for any streaming UI, voice agent (STT → LLM → TTS), or multilingual workload (Arabic, Urdu, Hindi, Indonesian). TTFT to user-visible content is ~45 ms, throughput ~30 tok/s. It is a `ForCausalLM` model with no thinking trace, so the first token shown to the user is also the first token the model generates.
- **`vllm/gpt-oss-20b`** — the default for long RAG answers and agent/tool flows. Throughput is ~98 tok/s (~3× qwen25), but TTFT to *user-visible content* is ~500 ms because the model emits hidden chain-of-thought in `delta.reasoning_content` before any `delta.content` token appears.

Two further models are explicitly **not recommended**:

- **Qwen3 variants** (`vllm/qwen3-*`, e.g. `redhataiqwen3-8b-fp8-dynamic`) emit a `<think>...</think>` block before the user-facing answer, eating most of the `max_tokens` budget. Useful only with a `--reasoning-parser qwen3` runtime arg, UI-side stripping, or when you switch to a non-thinking model.
- **Gemma 3n** (`vllm/gemma-3n-e4b`, `Gemma3nForConditionalGeneration`) is **broken** on the RHOAI-shipped vLLM (`0.13.0+rhai11`, `0.11.2+rhai5`) — it returns `completion_tokens > 0` but `content: ""` because the hybrid attention/SSM text decoder is not wired up. Stay on `ForCausalLM` architectures until a newer RHOAI vLLM image lands.

The embedding side is simpler: `granite-embedding-125m` (768-dim) is auto-registered by Llama Stack's `inline::sentence-transformers` provider and used for all RAG vector stores.

Model choice matters here because the stack supports both interactive (chat / voice) and batch-style (RAG) workloads on the same Llama Stack endpoint, and the right model depends on whether the user is waiting for the **first** word or the **last** word.

## Architecture & Design [coverage: high -- 3 sources]

### How models are deployed

LLMs run as KServe `InferenceService` resources. Each `InferenceService` brings up a vLLM serving runtime fronted by `kube-rbac-proxy` on port **8443** with a self-signed serving cert. Internal URLs follow the pattern `https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1`. Authentication uses an OpenShift service account token (`default-token-<isvc>-sa`); the `api_token: fake` placeholder built into the helm chart will be rejected with `Unauthorized`.

The embedding model (`granite-embedding-125m`) is **not** an InferenceService — it runs in-process inside the Llama Stack pod via the `inline::sentence-transformers` provider.

### How Llama Stack registers them

Llama Stack auto-registers the embedding model from `inline::sentence-transformers`, but **does not auto-register the vLLM-served LLM**. Without `vllm.modelId` set in the `helm/llama-stack` chart, `/v1/models` returns embeddings only and chat completions return `400 Bad Request: model field expected string`.

When `vllm.modelId` is set, Llama Stack registers the model with a **`vllm/` prefix** that clients must use:

| Helm value | What `/v1/models` exposes |
|------------|---------------------------|
| `vllm.modelId=qwen25-7b-instruct` | `vllm/qwen25-7b-instruct` |
| `vllm.modelId=gpt-oss-20b` | `vllm/gpt-oss-20b` |

Model name layout differs from the upstream genaiops chart, which prefixes with `vllm-<model>` (e.g. `vllm-llama32/llama32`). After switching charts, users have to re-select the model in Settings.

### Both config blocks need `tls_verify: false`

The vLLM provider config in `helm/llama-stack/templates/llama-stack.yaml` exists in two variants — guardrails-disabled and guardrails-enabled — and **both** must include `tls_verify: false` to talk to the kube-rbac-proxy's self-signed cert. Missing it produces a generic `APIConnectionError 500` on every chat completion even though `curl -k` from inside the llama-stack pod succeeds.

### Two independent paths

Llama Stack runs inference and safety on completely separate paths. The model section here is only the inference side:

```
Client → Llama Stack → remote::vllm provider → vLLM (kube-rbac-proxy :8443) → model
```

The safety/guardrails path (`remote::trusty_fms` → guardrails-orchestrator) does not touch vLLM. See the guardrails topic for that.

## Decisions & Rationale [coverage: high -- 3 sources]

### Why qwen25 for streaming UIs and voice

What matters in an interactive UI is *time-to-first-character-shown-to-the-user*, not raw throughput. Two specific reasons qwen25 wins on this axis:

- **No reasoning prologue.** qwen25 is a plain `ForCausalLM` model — the first sampled token is also the first content token. Measured TTFT to user-visible content is ~45 ms, well below the ~200 ms gap that humans perceive as a conversational pause.
- **Multilingual coverage.** qwen25 has stronger non-English support (Arabic, Urdu, Hindi, Indonesian) than gpt-oss, which is English-first.

For voice (STT → LLM → TTS), gpt-oss's 500 ms reasoning prologue creates dead air the user *will* hear as a pause. qwen25's 30 tok/s × ~100 tok ≈ 3.3 s response can be pipelined by the TTS layer, which only reads `delta.content` anyway.

### Why gpt-oss for long RAG and agents

The TTFT penalty amortizes over a long response. A 1000-token answer takes ~10 s on gpt-oss vs ~33 s on qwen25, so the half-second pause becomes negligible. The hidden reasoning trace also improves tool selection and multi-step planning for agent flows.

When gpt-oss might still win for voice: complex multi-step turns where reasoning is required (booking flow, calculation, tool invocation). Mitigation is to play a TTS filler ("let me check…") immediately after STT finalization while the LLM reasons in parallel.

### Don't use reasoning models in a UI that only reads `delta.content`

`gpt-oss-20b` (and Qwen3 in default mode) stream chain-of-thought tokens in `delta.reasoning_content` (and a legacy `delta.reasoning`) **separately** from `delta.content`. A naive client that only reads `delta.content` sees no output until the model finishes reasoning, even though tokens are arriving the whole time. Either surface reasoning under a collapsible "thinking" panel, strip it explicitly, or switch to a non-thinking model.

### Embedding model: `granite-embedding-125m`

Auto-registered via `inline::sentence-transformers`, so no helm config is required. The output dimension is **768** — set `embedding_dimension: 768` on vector store creation. Empty string causes `400 Bad Request`. Selecting the embedding model via the Settings UI (rather than editing `config.yaml` by hand) is recommended because the selectbox derives the dimension from live model metadata.

### Routing pattern (both models side-by-side)

Both InferenceServices can coexist. Llama Stack registers them as separate model IDs (`vllm/qwen25-7b-instruct`, `vllm/gpt-oss-20b`), so an application-level router can pick per turn — short conversational input → qwen25, longer or tool-flagged input → gpt-oss. No infrastructure changes needed, just a parameter change at request time.

## Operational Notes [coverage: high -- 2 sources]

### Register a model (helm flags)

The recipe (verbatim from `runbook.md`, "Deploy llama-stack with guardrails") sources the live cluster values on every upgrade — never reuse stale ones:

```bash
NS=user1-canopy
ISVC=qwen25-7b-instruct
TOKEN=$(oc get secret -n $NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d)
VLLM_URL="https://${ISVC}-predictor.${NS}.svc.cluster.local:8443/v1"

helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

The SA token must come from the **matching** InferenceService SA — using e.g. the whisper SA to call the qwen predictor authenticates as the wrong account and fails RBAC with `Forbidden (user=system:serviceaccount:<ns>:<wrong-sa>)`.

### Verify registration

```bash
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/models | jq '.data[].id'
```

The output must include the `vllm/`-prefixed LLM, not just embedding models. If it shows only embeddings, check `oc logs` on the llama-stack pod for `Unauthorized` during model auto-registration on startup.

### Pick the model in the UI

The `helm/llama-stack-ui` chart's `ui.defaultModel` value (and the Settings page in the running app) **must use the prefixed identifier**:

```bash
helm install llama-stack-ui helm/llama-stack-ui/ -n $NS \
  --set ui.defaultModel="vllm/qwen25-7b-instruct"
```

Anything that sends the model ID in chat completions has to use `vllm/<modelId>`, not the raw `<modelId>`.

### Add a second model side-by-side

Both InferenceServices can run in parallel, each with its own SA. Re-run the registration recipe with the second `ISVC` to add it. Llama Stack will expose both under `/v1/models` and the application can pick per turn. The chart only registers one LLM at a time via `vllm.modelId`; multi-model registration requires editing the `models:` block in the runtime config or chaining helm upgrades that mutate it.

### Service name caveat

The chart deploys a `LlamaStackDistribution` CR; the operator creates the Service as `llama-stack-service` (not `llama-stack`). Anything connecting from inside the cluster must use `http://llama-stack-service:8321`.

## Pitfalls & Known Issues [coverage: high -- 2 sources]

### Gemma 3n returns empty `content` on RHOAI vLLM (pitfall #20)

`gemma-3n-e4b` and other `Gemma3nForConditionalGeneration` models generate `completion_tokens: N` with `finish_reason: "length"` but `content: ""`. Affects `/v1/chat/completions` **and** raw `/v1/completions`, so it is not a chat template issue. Root cause: hybrid attention + SSM text decoder is not implemented correctly in `0.13.0+rhai11` / `0.11.2+rhai5` (`registry.redhat.io/rhaiis/vllm-cuda-rhel9` 3.x). **Workaround:** stay on `ForCausalLM` (Qwen2.5/Qwen3, Llama3, etc.) until a newer RHOAI vLLM image lands. Detect with `oc logs -l serving.kserve.io/inferenceservice=<isvc> -c kserve-container | grep "Resolved architecture"` — if it ends in `ForConditionalGeneration` and the runtime is < vLLM 0.14.0+, expect empty output.

### Qwen3 `<think>...</think>` eats `max_tokens` (pitfall #21)

`redhataiqwen3-8b-fp8-dynamic` and other Qwen3 variants emit a `<think>...</think>` reasoning trace before the user-facing response, consuming most of `max_tokens`. Things that **do not** work:

- `extra_body: {chat_template_kwargs: {enable_thinking: false}}` — Llama Stack silently drops `extra_body`; the kwarg never reaches vLLM.
- `messages: [{role: "system", content: "/no_think"}]` — model emits an empty `<think></think>` shell instead.
- `messages: [{role: "user", content: "... /no_think"}]` — same as above.

Things that **do** work:

- Direct vLLM call (bypassing Llama Stack) with `chat_template_kwargs: {enable_thinking: false}` — but loses Llama Stack abstractions (shields, RAG, conversations).
- Configure vLLM with `--reasoning-parser qwen3`. vLLM strips `<think>` from `content` and exposes it as `reasoning_content`. Requires editing the ServingRuntime args.
- Strip `<think>...</think>` in the UI before display.
- Switch to a non-thinking model (`qwen25-7b-instruct`).

### Reasoning models need `delta.reasoning_content` surfaced

`gpt-oss-20b` SSE chunks include `delta.reasoning_content` (and a legacy `delta.reasoning`) **in addition to** `delta.content`. A client that only reads `delta.content` will appear frozen until reasoning finishes. The current `modules/api.py` only reads `delta.content` — extending to read both is tracked in `docs/api-improvements.md`.

### Model name changes between charts

The genaiops chart names vLLM providers `vllm-<model>` (e.g. `vllm-llama32/llama32`). Our chart uses `vllm` (e.g. `vllm/llama32`). After switching charts, users must re-select the model in Settings — old IDs no longer resolve.

### `tls_verify: false` required (pitfall #17)

OpenShift InferenceServices expose vLLM behind kube-rbac-proxy on `:8443` with a self-signed serving cert. Both the guardrails-enabled and guardrails-disabled config blocks in `helm/llama-stack/templates/llama-stack.yaml` need `tls_verify: false`. The non-guardrails block had it from the start; the guardrails-enabled block was missing it for a while, causing `APIConnectionError 500` despite curl working from inside the pod. Verify with:

```bash
oc get cm llama-stack-config -n <ns> -o jsonpath='{.data.config\.yaml}' | grep -A3 'provider_id: vllm'
```

Three keys must appear: `url`, `api_token`, `tls_verify`.

### Stale `vllm.modelId` from `--reuse-values` (pitfall #24)

`helm upgrade --reuse-values` carries forward stale `vllm.url`, `vllm.apiToken`, and `vllm.modelId`. After someone swaps the running InferenceService (Qwen3 stopped, Qwen2.5 started) or rotates the SA token, these reused values silently desync, producing `APIConnectionError` (DNS) or `404 model not found`. Always re-source on every upgrade:

```bash
TOKEN=$(oc get secret -n <ns> default-token-<isvc>-sa -o jsonpath='{.data.token}' | base64 -d)
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set vllm.url="https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="<isvc>"
```

Detect with `helm get values llama-stack -n <ns> | grep -E 'url|modelId'` — if the URL or modelId references an InferenceService that no longer exists (or is `Stopped`), this is it.

### Small-context models overflow on first message

Defaults (`max_tokens` ≈ 2000) nearly equal the entire context window for models like `qwen25-vl-7b-instruct` (2024 token context). The UI's `get_model_context_length()` probes the actual window on first use and caps `effective_max_tokens` to `context_length // 2`, then trims conversation history to fit. If `get_model_context_length()` returns `None` (probe timeout, non-standard error format), context management silently degrades.

### `/v1/models` only lists the embedding model (pitfall #16)

Symptom: UI's model dropdown is empty (or only embeddings). Sending chat with `model=null` returns `400 Bad Request: {"loc":["body","model"], "msg":"Input should be a valid string"}`. Cause: `vllm.modelId` not set, so the LLM was never declared in the runtime config's `models:` block. Fix: set `vllm.modelId` and verify with `curl -s $LLAMA_STACK/v1/models | jq '.data[] | select(.model_type=="llm") | .identifier'`.

### Wrong SA token (pitfalls #8, #13)

Two distinct failure modes:

- `api_token: fake` (helm chart default) → Llama Stack returns `{"detail": "Unauthorized"}`. Fix: set `vllm.apiToken` to the real SA token.
- Wrong SA token (e.g. whisper SA used for qwen predictor) → `{"detail": "Forbidden (user=system:serviceaccount:<ns>:<wrong-sa>)"}`. Fix: match SA name to InferenceService name — `default-token-<inferenceservice-name>-sa`.

## Findings & Measurements [coverage: high -- 1 source]

Benchmarks below were collected hitting each model's vLLM endpoint **directly** (bypassing Llama Stack) from inside an in-cluster pod, so the numbers reflect model + runtime, not the routing layer. Methodology: 1 warmup + 3 measured runs per (prompt size × mode), `temperature=0`, three prompt sizes (short ≤20 tok, medium 100 tok, long 250 tok), runtime image `RHOAI vLLM 0.13.0+rhai11`.

### 2026-05 — Throughput, non-streaming, full completion

| Prompt | max_tokens | qwen25-7b-instruct | gpt-oss-20b |
|--------|-----------|--------------------|-------------|
| short  | 20  | 0.31 s · 29 tok/s | **0.23 s · 88 tok/s** |
| medium | 100 | 3.33 s · 30 tok/s | **1.04 s · 96 tok/s** |
| long   | 250 | 8.32 s · 30 tok/s | **2.55 s · 98 tok/s** |

`gpt-oss-20b` is ~3× faster end-to-end despite being the larger model — likely a Mixture-of-Experts effect (only a fraction of the parameters activate per token).

### 2026-05 — TTFT to first user-visible content (streaming)

| Prompt | qwen25-7b-instruct | gpt-oss-20b |
|--------|--------------------|-------------|
| short  | **45 ms** | 499 ms (reasoning first) |
| medium | **45 ms** | 499 ms |
| long   | **46 ms** | content arrives only at end (~2.5 s) |

`qwen25-7b-instruct` starts emitting visible characters in tens of milliseconds. `gpt-oss-20b` spends the first part of every response on hidden chain-of-thought before any user-facing token appears. For long prompts, the user-visible content for gpt-oss only arrives at the *end* of the ~2.5 s window because reasoning consumes the budget.

### 2026-05 — TTFT to first token of any kind (reasoning + content)

| Prompt | qwen25-7b-instruct | gpt-oss-20b |
|--------|--------------------|-------------|
| short  | 45 ms | 63 ms |
| medium | 45 ms | 62 ms |
| long   | 46 ms | 50 ms |

Both models start producing *some* output within ~50 ms. The difference is *what* they emit first — qwen25 emits content immediately; gpt-oss emits reasoning_content tokens first.

### 2026-05 — Variance and caveats

- Single-GPU, no concurrent load. Numbers degrade under contention; relative ranking should hold.
- Variance across runs was **< 5 ms** with warm KV cache. **Cold-start TTFT is significantly higher** — the first request after pod start can take seconds.
- These are RHOAI vLLM `0.13.0+rhai11` numbers. Newer/older runtime images will differ.
- `Gemma3nForConditionalGeneration` models produce empty content on this runtime (pitfall #20) — excluded from comparison.
- Qwen3 (`redhataiqwen3-8b-fp8-dynamic`) emits `<think>...</think>` blocks before content even though it's not labeled a reasoning model (pitfall #21). Behavior is similar to gpt-oss for TTFT purposes; treat it the same way.

### 2026-05 — Use-case routing summary

- **Voice agent / streaming UI / multilingual** → `qwen25-7b-instruct` (45 ms TTFT to user-visible content).
- **Long RAG (~1000 token answers)** → `gpt-oss-20b` (~10 s vs ~33 s; TTFT penalty amortized).
- **Agent / tool-using flows** → `gpt-oss-20b` (hidden reasoning improves tool selection, throughput matters more on longer turns).
- **English-only short chat where throughput dominates feel** → either; default to qwen25 unless the workload is consistently long.

## Sources

- [components.md](../../wiki/components.md)
- [model-benchmarks.md](../../wiki/model-benchmarks.md)
- [decisions.md](../../wiki/decisions.md)
- [runbook.md](../../wiki/runbook.md)
- [pitfalls.md](../../wiki/pitfalls.md)
