# Model Benchmarks

Per-model latency and throughput observations on the available RHOAI vLLM runtime. Numbers are for orientation, not contracts — they reflect the specific image build, GPU, and KV cache state at measurement time. Re-measure if any of those change.

---

## Methodology

All numbers below were collected by hitting each model's vLLM endpoint **directly** (bypassing Llama Stack) from inside an in-cluster pod. Direct calls remove orchestrator overhead so the measured times reflect the model + runtime, not the routing layer.

- 1 warmup request, then 3 measured runs per (prompt size × mode)
- `temperature=0` (greedy decoding) for reproducibility
- 3 prompt sizes: short (`What is 2+2?`, ≤20 tok), medium (paragraph, 100 tok), long (essay, 250 tok)
- Two modes: non-streaming (full completion latency) and streaming (TTFT)
- TTFT measured two ways for reasoning models: time to first **content** token vs time to first token **of any kind** (reasoning_content counts)

The benchmark script lives at `tools/bench-vllm.py` (or recreate it from the recipe at the bottom of this page).

---

## Results

### Throughput (non-streaming, full completion)

| Prompt | max_tokens | qwen25-7b-instruct | gpt-oss-20b |
|--------|-----------|--------------------|-------------|
| short  | 20  | 0.31 s · 29 tok/s | **0.23 s · 88 tok/s** |
| medium | 100 | 3.33 s · 30 tok/s | **1.04 s · 96 tok/s** |
| long   | 250 | 8.32 s · 30 tok/s | **2.55 s · 98 tok/s** |

`gpt-oss-20b` is ~3× faster end-to-end despite being the larger model. Likely a Mixture-of-Experts effect (only a fraction of the parameters activate per token).

### TTFT to first user-visible content (streaming)

| Prompt | qwen25-7b-instruct | gpt-oss-20b |
|--------|--------------------|-------------|
| short  | **45 ms** | 499 ms (reasoning first) |
| medium | **45 ms** | 499 ms |
| long   | **46 ms** | content arrives only at end (~2.5 s) |

`qwen25-7b-instruct` starts emitting visible characters in tens of milliseconds. `gpt-oss-20b` spends the first part of every response on hidden chain-of-thought before any user-facing token appears.

### TTFT to first token of any kind (reasoning + content)

| Prompt | qwen25-7b-instruct | gpt-oss-20b |
|--------|--------------------|-------------|
| short  | 45 ms | 63 ms |
| medium | 45 ms | 62 ms |
| long   | 46 ms | 50 ms |

Both models start producing some output within ~50 ms — the difference is *what* they emit first.

---

## Reasoning models stream `reasoning_content` separately

`gpt-oss-20b` SSE chunks include `delta.reasoning_content` (and a legacy `delta.reasoning`) in addition to `delta.content`. A naive client that only reads `delta.content` will see no output until the model finishes reasoning, even though tokens are arriving the entire time.

For a UI that wants to show "thinking" indicators or a collapsible reasoning panel, the streaming reader has to handle both fields. Our `modules/api.py` currently only reads `delta.content` — see `docs/api-improvements.md` if extending this becomes a priority.

---

## Recommendation by use case

### Voice agent (STT → LLM → TTS pipeline) → `qwen25-7b-instruct`

What matters for voice is **time-to-first-spoken-word**, which is dominated by the LLM's TTFT to user-facing content (TTS waits on actual content, not reasoning chunks).

- qwen25's 45 ms TTFT is below the ~200 ms gap that humans perceive as a conversational pause. The agent feels responsive.
- gpt-oss's 500 ms reasoning prologue creates dead air the user *will* hear as a pause — even though gpt-oss's overall throughput is higher.
- Voice replies are short (1–3 sentences, ~50–150 tokens). qwen25's 30 tok/s × 100 tok = 3.3 s of audio generation, which TTS can pipeline over.
- qwen25 has stronger non-English support (Arabic, Urdu, Hindi, Indonesian) than gpt-oss, which is English-first.

When gpt-oss might still win for voice: complex multi-step turns where reasoning is required (booking flow, calculation, tool invocation). Mitigate the dead-air problem by playing a TTS filler ("let me check…") immediately after STT finalization while the LLM reasons in parallel.

### Plain text chat with no agent → `qwen25-7b-instruct`

Same logic — perceived speed comes from streaming feel, not throughput.

### Agent / tool-using flows → `gpt-oss-20b`

The hidden reasoning improves tool selection and multi-step planning, and the higher throughput matters more when responses are longer.

### RAG with long contexts → `gpt-oss-20b`

A 1000-token answer takes ~10 s on gpt-oss vs ~33 s on qwen25. The reasoning prologue is amortized across a much longer response, so the TTFT difference becomes negligible.

### Routing pattern (if you want both)

Both InferenceServices can coexist. Register both in Llama Stack and let the application pick per turn — short conversational input → qwen25, longer or tool-flagged input → gpt-oss. Llama Stack treats them as separate model IDs (`vllm/qwen25-7b-instruct`, `vllm/gpt-oss-20b`), so switching is just a parameter change at request time.

---

## Caveats and known issues

- Single-GPU, no concurrent load. Numbers will degrade under contention; the relative ranking should hold.
- Variance across runs was < 5 ms — KV cache was warm. Cold-start TTFT is significantly higher (the first request after pod start can take seconds).
- These are RHOAI vLLM 0.13.0+rhai11 numbers. Newer/older runtime images will differ.
- `Gemma3nForConditionalGeneration` models produce empty content on this runtime — see pitfall 20. Don't include them in any voice-agent comparison until the runtime is upgraded.
- Qwen3 (`redhataiqwen3-8b-fp8-dynamic`) emits `<think>...</think>` blocks before content even though it's not labeled a reasoning model — see pitfall 21. Behavior is similar to gpt-oss for TTFT purposes; treat it the same way.

---

## Reproducing the measurement

The benchmark script reads the vLLM URL, SA token, model identifier, and a label as positional arguments, runs the matrix, and prints a table. It uses only the standard library so it can run inside the llama-stack pod with no extra packages.

Quickstart:

```bash
# 1. Get the SA token for the InferenceService
TOKEN=$(oc get secret -n <ns> default-token-<isvc>-sa \
  -o jsonpath='{.data.token}' | base64 -d)

# 2. Copy the bench script into the llama-stack pod (cluster DNS + curl-like access)
oc cp ./bench.py <ns>/<llama-stack-pod>:/tmp/bench.py

# 3. Run against the in-cluster vLLM URL
oc exec -n <ns> deployment/llama-stack -- python3 /tmp/bench.py \
  "https://<isvc>-predictor.<ns>.svc.cluster.local:8443" \
  "$TOKEN" \
  "<served-model-name>" \
  "<human-readable-label>"
```

Hit each model with the same script and same prompts to keep results comparable.
