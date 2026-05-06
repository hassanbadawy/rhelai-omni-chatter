# Pitfalls Log

Each entry: symptom, root cause, fix applied, and how to detect it again.

---

## 1. Responses API silently ignores `max_tokens`

**Symptom:** Model always generates a fixed-length response regardless of `max_tokens` setting. Truncation or long output can't be controlled.

**Root cause:** The Llama Stack Responses API (`/v1/responses`) does not forward `max_output_tokens` to the vLLM backend. The vLLM adapter uses its own `VLLM_MAX_TOKENS` env var set at server startup time.

**Fix:** Switched to Chat Completions API (`/v1/chat/completions`), which passes `max_tokens` through correctly.

**How to detect again:** If you ever re-enable the Responses API, test by setting `max_tokens=10` and checking if the response is actually short.

---

## 2. Streamlit selectbox crashes with `StreamlitAPIException` after endpoint change

**Symptom:** Settings page crashes with an index error on the model/embedding/VIO selectbox after switching to a different Llama Stack endpoint that has different models.

**Root cause:** Streamlit's `st.selectbox` with an explicit `key` caches the last selected value in session state. When the options list changes (new endpoint, different models), the cached value may no longer be in the new list, causing `index` to be out of range or the widget to return a stale value silently.

**Fix:** Before rendering each selectbox, check if the cached session state value is still in the new options list:
```python
if "settings_model" in st.session_state and st.session_state["settings_model"] not in model_ids:
    del st.session_state["settings_model"]
```

**Files:** `pages/settings.py` — applied to `settings_model`, `settings_embedding`, `settings_vio` keys.

---

## 3. Small context models overflow on first message

**Symptom:** First message to a model fails with a context length error. Affects models like `qwen25-vl-7b-instruct` (2024 token context window).

**Root cause:** The default `max_tokens` in config (e.g. 2000) nearly equals the model's entire context window. Even a short system prompt + user message + 2000 requested output tokens exceeds the limit.

**Fix:** `get_model_context_length()` in `api.py` probes the model's actual context window on first use and caches it. `chat.py` caps `effective_max_tokens` to `context_length // 2` and trims conversation history to fit.

**How to detect again:** A new model fails on the first message with "maximum context length is N tokens" in the error. Check if `get_model_context_length()` returned `None` for it (probe may have failed due to timeout or non-standard error format).

---

## 4. Server errors arrive as HTTP 200 inside the SSE stream

**Symptom:** A chat request appears to succeed (HTTP 200), but no text is displayed and the stream silently ends. Or: an error message appears mid-stream.

**Root cause:** The Llama Stack server can encode errors as a JSON object `{"error": {"message": "..."}}` inside an SSE `data:` line, with the outer HTTP response still being 200. The original code swallowed these by catching `KeyError` and `IndexError` broadly.

**Fix:** `chat_completions_stream()` in `api.py` now explicitly checks for the `"error"` key in each parsed chunk and raises `RuntimeError` with the message. `_create_response_stream()` handles the `"response.failed"` SSE event type similarly.

---

## 5. Model context length not in metadata

**Symptom:** `get_model_context_length()` logs "Model X metadata keys: []" or similar and falls through to the probe.

**Root cause:** The vLLM inference adapter in Llama Stack does not consistently populate context length fields in the `/v1/models` response. The field name also varies: `max_seq_len`, `context_length`, `max_model_len`, `context_window` are all observed across different server versions.

**Fix:** The method checks all four key names and falls back to a probe request. If both fail, it returns `None` and context management is skipped.

---

## 6. Conversation messages lost on page refresh

**Symptom:** User refreshes the browser tab and all chat history disappears. Conversation names are still in the sidebar but the chats are empty.

**Root cause:** By design — message history lives only in `st.session_state.conversations`, which is reset on every Streamlit page load. `conversations.json` stores only display names (see `docs/entanglements.md`).

**Fix (not yet applied):** Serialize messages to a local file or use the Llama Stack Conversations API. See `docs/api-improvements.md` item 4.

---

## 8. vLLM `api_token: fake` causes `Unauthorized` from Llama Stack

**Symptom:** Chat completions through Llama Stack return `{"detail": "Unauthorized"}` even though the vLLM endpoint is reachable.

**Root cause:** The helm chart default sets `api_token: fake`. On OpenShift, vLLM InferenceServices use OpenShift service account token auth. `fake` is rejected by the predictor's auth middleware.

**Fix:** Set `vllm.apiToken` in the llama-stack helm to the SA token from the InferenceService's service account secret:
```bash
oc get secret -n <ns> default-token-<inferenceservice-name>-sa -o jsonpath='{.data.token}' | base64 -d
```
Use the token from the **matching** InferenceService SA — not a different service's SA (e.g. whisper SA won't work for qwen predictor).

**How to detect again:** Llama Stack `/v1/models` only shows the embedding model, not the vLLM model. Check `oc logs` on the llama-stack pod for `Unauthorized` when it tries to auto-register models from vLLM on startup.

---

## 9. `shields: null` in Llama Stack config causes `ValidationError` on startup

**Symptom:** New llama-stack pod crashes immediately with `pydantic_core.ValidationError: shields — Input should be a valid list`.

**Root cause:** When `guardrails.enabled=true` but no individual shield flags are set (`hap.enabled`, `regex.enabled`, etc.), the helm template renders `shields:` with nothing after it — YAML null, not an empty list `[]`.

**Fix:** The template uses a `$shieldsEmpty` flag to emit `shields: []` when no shields are enabled. If this regresses, check `helm template` output for `shields:` followed by a blank line.

---

## 10. `confidence_threshold` blank causes `'>' not supported between 'float' and 'NoneType'`

**Symptom:** Shield returns `status: error` with Python comparison error for every message. Clean inputs pass but violated inputs error instead of returning `violation`.

**Root cause:** When shields are enabled via `--set guardrails.hap.enabled=true` without also setting `--set guardrails.hap.confidence_threshold=0.5`, the threshold renders as empty in the config. The `trusty_fms` provider then passes `None` as the threshold to the comparison logic.

**Fix:** Always set confidence thresholds explicitly when enabling shields:
```bash
--set guardrails.hap.confidence_threshold=0.5
--set guardrails.prompt_injection.confidence_threshold=0.5
--set guardrails.language_detection.confidence_threshold=0.85
--set guardrails.regex.confidence_threshold=0.5
```

---

## 11. Guardrails detector runtime expects `MODEL_DIR`, not `DETECTOR_MODEL_ID`

**Symptom:** Detector pods crash with `ValueError: MODEL_DIR environment variable is not set`.

**Root cause:** `quay.io/trustyai/guardrails-detector-huggingface-runtime` does **not** pull models from HuggingFace at startup. It calls `AutoTokenizer.from_pretrained(model_files_path)` where `model_files_path = os.environ.get("MODEL_DIR")` — a local filesystem path. The model must already be on disk.

**Fix:** Use an initContainer with the same runtime image to call `snapshot_download()` into an `emptyDir` volume mounted at `/mnt/models`, then set `MODEL_DIR=/mnt/models` on the main container. The initContainer needs 4Gi memory limit (language-detection OOMs at 2Gi).

**How to detect again:** Pod is in `Init:Error` or `Init:CrashLoopBackOff`. Check initContainer logs for the `MODEL_DIR` error or OOMKilled.

---

## 12. `chunker.hostname` set to a non-service value breaks orchestrator startup

**Symptom:** Guardrails orchestrator crashes with `invalid config file: chunkers.sentence: missing field 'service'`.

**Root cause:** The chunker config block requires a valid `service:` sub-block with `hostname` and `port`. Leaving it blank (or setting it to a namespace name like `agentic-ivr`) renders malformed YAML that the orchestrator rejects.

**Fix:** The configmap template always renders a fallback `service: hostname: 127.0.0.1, port: 8085` when `chunker.hostname` is empty. Leave `chunker.hostname: ""` unless you have an actual chunker service deployed.

---

## 13. Wrong SA token used for vLLM auth

**Symptom:** Llama Stack returns `{"detail": "Forbidden (user=system:serviceaccount:<ns>:<wrong-sa>)"}` — authenticates but gets RBAC denied.

**Root cause:** The wrong service account token was set in the helm upgrade. Each InferenceService has its own SA (e.g. `redhataiqwen3-8b-fp8-dynamic-sa`). Using the whisper SA token to call the qwen predictor authenticates as the whisper SA, which has no permission on the qwen InferenceService.

**Fix:** Match the SA name to the InferenceService name: `default-token-<inferenceservice-name>-sa`.

---

## 14. `remote::passthrough` is incompatible with IBM/FMS guardrails detectors

**Symptom:** Attempting to use `remote::passthrough` as the Llama Stack safety provider against the FMS guardrails orchestrator fails — no violations are ever detected.

**Root cause:** `remote::passthrough` calls `POST /moderations` (OpenAI format). FMS orchestrator exposes `POST /api/v2/text/detection/content` (IBM format). Completely different request/response schemas.

**Fix:** Use `remote::trusty_fms` (only available in the custom `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms` image). Requires `guardrails.enabled=true` in the llama-stack helm chart.

---

## 7. `embedding_dimension` mismatch on vector store creation

**Symptom:** Vector store creation fails or embeddings don't match when searching.

**Root cause:** The embedding dimension must match the model's actual output dimension. The Settings page reads `embedding_dimension` from the model's metadata, but if the user edits `config.yaml` manually or the metadata is missing, the stored dimension may be wrong.

**Fix:** Always select the embedding model via the Settings UI rather than editing `config.yaml` directly. The selectbox derives dimension from live model metadata.

---

## 15. Container `config.yaml` shadows env-var defaults

**Symptom:** Helm chart sets `LLAMA_STACK_API_ENDPOINT` env var but the deployed UI keeps trying to connect to the old endpoint baked into `config.yaml` that shipped with the image.

**Root cause:** `modules/config.py` loads `config.yaml` first and only falls back to env vars when the YAML key is missing. The image bakes in a developer's local `config.yaml` (with their personal endpoint), so env var overrides are silently ignored.

**Fix:** Two complementary changes —
1. `load_config()` now treats empty-string values in YAML as "not set" and pulls from env (`LLAMA_STACK_API_ENDPOINT`, `DEFAULT_MODEL`).
2. The chart sets `LLAMA_STACK_UI_DATA_DIR=/tmp/llama-stack-ui-data` so the loader writes/reads from a fresh empty dir, bypassing the baked YAML entirely. Settings page edits then persist there until pod restart.

**How to detect again:** After deploying, exec into the pod and run `python3 -c "from modules.config import load_config; print(load_config())"`. If `endpoint` shows the developer URL instead of the chart-supplied one, the YAML is shadowing env vars.
