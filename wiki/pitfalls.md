# Pitfalls Log

---

## 27. aiosqlite `executescript()` auto-commits — migration record must be written separately

**Symptom:** On app restart after a crash mid-migration, `RuntimeError: Migration v002_redesign.sql failed: table materials_v2 already exists`. The migration had already been applied to the DB but was never recorded in `schema_migrations`, so the runner tried again.

**Root cause:** SQLite's `executescript()` issues a `COMMIT` before running, voiding any `BEGIN` issued beforehand. The v002 migration ran and committed, but the `INSERT INTO schema_migrations` that follows in Python was never reached (crash or exception). On next launch the runner sees v002 as pending and tries again — `materials_v2` already exists.

**Fix (two-part):**
1. Remove the `BEGIN;` call before `executescript()` — it's a no-op and misleading.
2. Make the migration SQL idempotent: use `CREATE TABLE IF NOT EXISTS materials_v2` instead of `CREATE TABLE materials_v2`. This makes the migration safe to re-run.

**Files:** [`services/storage.py`](../student-assistant/services/storage.py) lines 181-188, [`migrations/v002_redesign.sql`](../student-assistant/migrations/v002_redesign.sql) line 20.

---

## 26. `FloatingActionButton` in Flet 0.85.1 does not accept `text=`

**Symptom:** `TypeError: FloatingActionButton.__init__() got an unexpected keyword argument 'text'` on every route that shows an FAB.

**Root cause:** Flet 0.85.1 removed the `text` parameter from `FloatingActionButton`. There is no labelled FAB equivalent (no `ExtendedFloatingActionButton`). Use `tooltip=` for hover text and icon-only appearance.

**Fix:** Replace `text="Label"` with `tooltip="Label"` in all FAB declarations.

---

## 25. Flet 0.85.1 breaks student-assistant code written for Flet 0.26

**Symptom:** `student-assistant` starts (HTTP 200) but every browser session crashes with a cascade of `AttributeError` / `TypeError` errors. Each fix reveals the next one.

**Root cause:** The flet package installed by `uv sync` (≥0.80) is a near-complete rewrite. Module-level helpers (`ft.alignment`, `ft.padding`, `ft.margin`, `ft.border`) became plain Python modules whose helpers moved onto the class. Button and FilePicker APIs changed. The session storage API moved one level deeper.

**Complete list of breaking changes (0.26 → 0.85.1) hit in student-assistant:**

| Old (0.26) | New (0.85.1) | Affected files |
|---|---|---|
| `page.session.set/get(k, v)` | `page.session.store.set/get(k, v)` | `app.py`, all views |
| `ft.alignment.center` | `ft.Alignment.CENTER` | `materials_list`, `wiki_tab`, `chat_tab`, `streaming_bubble` |
| `ft.alignment.center_left/right` | `ft.Alignment.CENTER_LEFT/RIGHT` | `streaming_bubble` |
| `ft.padding.symmetric(h=, v=)` | `ft.Padding.symmetric(horizontal=, vertical=)` | `wiki_tab`, `chat_tab`, `material_card`, `streaming_bubble` |
| `ft.padding.only(left=)` | `ft.Padding.only(left=)` | `wiki_tab` |
| `ft.margin.only(...)` | `ft.Margin.only(...)` | `streaming_bubble` |
| `ft.border.only(...)` | `ft.Border.only(...)` | `chat_tab` |
| `ft.border.BorderSide(...)` | `ft.BorderSide(...)` | `chat_tab` |
| `Button(text="…")` | `Button(content="…")` | `upload_modal`, `materials_list` |
| `FilePicker(on_result=cb)` | `files = await picker.pick_files(with_data=True)` | `upload_modal` |
| `page.overlay.append(picker)` | `page.services.append(picker)` | `upload_modal` |
| `page.dialog = d; d.open = True` | `page.show_dialog(d)` | `upload_modal` |
| `dialog.open = False; page.update()` | `page.pop_dialog()` | `upload_modal` |

**Additional:** `flet run --web` fails with `ModuleNotFoundError: No module named 'flet_desktop'` when only `flet_web` is installed (the CLI imports desktop unconditionally). Workaround: launch via `python app.py` with `ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080)` in `_run()`. `ft.app()` itself is deprecated since 0.80 in favour of `ft.run()` but still functions.

**Web-mode file bytes:** In Flet web mode, `FilePickerFile.path` is always `None`. Use `pick_files(with_data=True)` and read `FilePickerFile.bytes` instead of reading the path from disk.

**Fix:** All of the above are applied in `student-assistant/` as of 2026-05-16. Pin `flet>=0.85.1` in `pyproject.toml` once the version is stable enough to lock.

**How to detect again:** `uv run python -c "import flet; print(flet.__version__)"` — if ≥0.80 and code was written for <0.80, expect all of the above to fail on first browser load.

---

## 26. Podman compose needs `host.containers.internal`, not `host.docker.internal`

**Symptom:** `podman compose up -d` starts containers but Llama Stack cannot reach Ollama; requests to `http://host.docker.internal:11434` time out.

**Root cause:** Podman on macOS maps the host as `host.containers.internal`, not `host.docker.internal`. The `docker-compose.yml` in `student-assistant/` originally used the Docker name for `OLLAMA_URL` and `extra_hosts`.

**Fix:** Replace both occurrences in `student-assistant/docker-compose.yml`:
```yaml
# Before
OLLAMA_URL: "http://host.docker.internal:11434"
extra_hosts:
  - "host.docker.internal:host-gateway"

# After
OLLAMA_URL: "http://host.containers.internal:11434"
extra_hosts:
  - "host.containers.internal:host-gateway"
```

Podman 5.7.1 ships with a built-in compose engine (Docker Compose v5.1.0 via `podman compose`). No separate `podman-compose` package needed.

**How to detect again:** Llama Stack logs show `ConnectionRefused` or timeout connecting to port 11434. Confirm with `podman exec student-assistant-llama-stack curl -s http://host.docker.internal:11434` — if it fails and `host.containers.internal` works, this is the issue.

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

---

## 16. Llama Stack `/v1/models` only lists embedding models, never the LLM

**Symptom:** UI's model dropdown is empty (or only shows embedding models). Sending a chat with `model=null` returns:
```
400 Bad Request: {"loc":["body","model"], "msg":"Input should be a valid string"}
```

**Root cause:** The `helm/llama-stack` chart had no `vllm.modelId` value and never registered the LLM model in the runtime config. Llama Stack auto-registers the *embedding* model (sentence-transformers) but the vLLM-served LLM has to be declared explicitly in the `models:` section of the runtime config.

**Fix:** Added `vllm.modelId` to `values.yaml` and a `provider_id: vllm` model entry to both config blocks (guardrails-enabled and disabled) in `templates/llama-stack.yaml`. Verify with:
```bash
curl -s $LLAMA_STACK/v1/models | jq '.data[] | select(.model_type=="llm") | .identifier'
```

**Caveat:** Llama Stack registers the model with a `vllm/` prefix (e.g. `vllm/<modelId>`). Anything that needs to send the model ID in chat completions must use the prefixed identifier, not the raw `modelId` value.

---

## 17. `tls_verify` missing in guardrails-mode vLLM provider config

**Symptom:** Llama Stack returns `Internal Server Error` 500 with `APIConnectionError: Connection error` for every chat completion. The vLLM predictor is up and reachable from inside the llama-stack pod with curl, but llama-stack itself fails.

**Root cause:** OpenShift InferenceServices expose vLLM behind a kube-rbac-proxy on port 8443 with a self-signed serving cert. The default `httpx`/openai client verifies TLS. Without `tls_verify: false` in the vLLM provider config, every connection fails the cert check.

The non-guardrails config block had `tls_verify: {{ .Values.vllm.tlsVerify }}`. The guardrails-enabled block did not — it only rendered `url` and `api_token`. Same chart, different config blocks, only one was correct.

**Fix:** Added `tls_verify: {{ .Values.vllm.tlsVerify }}` to the guardrails-enabled block in `templates/llama-stack.yaml`. Verify with:
```bash
oc get cm llama-stack-config -n <ns> -o jsonpath='{.data.config\.yaml}' | grep -A3 'provider_id: vllm'
```
Should show three keys: `url`, `api_token`, `tls_verify`.

**How to detect again:** From inside the llama-stack pod, raw `curl -k` to the vLLM URL works but llama-stack's own connections fail. The error message in llama-stack logs is generic `APIConnectionError`, not a TLS-specific one — easy to misdiagnose as a routing issue.

---

## 18. Operator-managed Llama Stack service is named `llama-stack-service`, not `llama-stack`

**Symptom:** Playground/UI pod logs show `APIConnectionError`. Inside the pod, `nslookup llama-stack` fails (DNS exit code 6) but `nslookup llama-stack-service` succeeds.

**Root cause:** When Llama Stack is deployed via the `llama-stack-k8s-operator` (i.e. via a `LlamaStackDistribution` CR, which is what our chart creates), the **operator** generates the Service — and it names the service `<name>-service`, not the same as the deployment.

The `helm/llama-stack-playground` chart originally defaulted `playground.llamaStackUrl` to `http://llama-stack:8321`, which only matches a deployment-as-service pattern (i.e. helm-only, no operator). For operator-managed installs the URL has to be `http://llama-stack-service:8321`.

**Fix:** Both `helm/llama-stack-playground/values.yaml` and `helm/llama-stack-ui/values.yaml` default `llamaStackUrl` / `ui.llamaStackUrl` to `http://llama-stack-service:8321`.

**How to detect again:** `oc get svc -n <ns> | grep llama-stack` — operator deployments show only `llama-stack-service`, helm-only deployments show `llama-stack`.

---

## 19. Genaiops playground 0.3.0-fix file upload crashes with `AttributeError: 'dict' object has no attribute 'content'`

**Symptom:** Uploading a file in the genaiops playground (`/app/llama_stack/distribution/ui/page/upload/upload.py:59`) crashes with `AttributeError`. Streamlit shows a traceback and the vector store is created without any documents.

**Root cause:** The code does `BytesIO(doc.content.encode('utf-8'))` where `doc` is a `RAGDocument`. In `llama-stack-client` 0.3.0, `RAGDocument(...)` returns a plain `dict`, not an object — so `doc.content` raises `AttributeError`. The right access is `doc['content']`.

**Fix:** Not fixable in the genaiops image (read-only, third-party). Three options:
1. Use our `llama-stack-ui` instead — `documents.py` uses dict-safe `.get()` access patterns.
2. Build a patched genaiops image with `doc['content']`.
3. Mount a patched `upload.py` via ConfigMap volume over the broken one.

We chose option 1 — see decision 7.

**How to detect again:** Watch for `AttributeError: 'dict' object has no attribute 'content'` in any code that constructs `RAGDocument` and immediately reads `.content`. The dict-vs-object split in the SDK affects more than just RAGDocument; any instance access on SDK return types should be guarded with `isinstance` or `.get()`.

---

## 20. Gemma 3n produces empty content on RHOAI-shipped vLLM builds

**Symptom:** `gemma-3n-e4b` (and `Gemma3nForConditionalGeneration` models in general) generate `completion_tokens: N` with `finish_reason: "length"` but `content: ""`. Affects both `/v1/chat/completions` and the raw `/v1/completions` endpoint, so it is not a chat template issue.

**Root cause:** The model is registered in vLLM as `Gemma3nForConditionalGeneration` — a multimodal architecture with a hybrid attention + SSM-style mixer (`cache_implementation: hybrid` in `generation_config.json`). The RHOAI-shipped vLLM builds (`0.13.0+rhai11` and `0.11.2+rhai5`, packaged as `registry.redhat.io/rhaiis/vllm-cuda-rhel9` 3.x) do not implement the text decoder for this hybrid architecture correctly. Tokens are sampled but decoded to empty strings.

**Fix:** Stay on a non-multimodal architecture (e.g. `Qwen2.5ForCausalLM`, `Qwen3ForCausalLM`) until a newer RHOAI vLLM image lands. Verify with:
```bash
oc logs -l serving.kserve.io/inferenceservice=<isvc> -c kserve-container | grep "Resolved architecture"
```
If the architecture name ends in `ForConditionalGeneration` and the runtime image is < vLLM 0.14.0+, expect empty output.

**How to detect again:** A quick `curl -X POST .../v1/completions` with a plain prompt returning `{"text":"", "finish_reason":"length"}` is the smoking gun.

---

## 21. Qwen3 thinking mode: `<think>...</think>` blocks consume `max_tokens` and clutter output

**Symptom:** `redhataiqwen3-8b-fp8-dynamic` chat output starts with a long `<think>...</think>` block, eating most of the `max_tokens` budget before the actual answer begins.

**Root cause:** Qwen3 has a default reasoning mode that emits a thinking trace before the user-facing response. The `<think>` block is part of the model's actual output, not metadata.

**Fix attempts ranked:**
- ❌ `extra_body: {chat_template_kwargs: {enable_thinking: false}}` — Llama Stack silently drops `extra_body`; the kwarg never reaches vLLM.
- ❌ `messages: [{role: "system", content: "/no_think"}]` — model emits an empty `<think></think>` shell instead of suppressing it.
- ❌ `messages: [{role: "user", content: "... /no_think"}]` — same as above.
- ✓ Direct vLLM call (bypassing Llama Stack) with `chat_template_kwargs: {enable_thinking: false}` — works, but loses the Llama Stack abstractions (shields, RAG, conversations).
- ✓ Configure vLLM with `--reasoning-parser qwen3` and let it strip `<think>` from `content` → exposes them as `reasoning_content` separately. Requires editing the ServingRuntime args.
- ✓ Strip `<think>...</think>` in the UI before displaying — easiest if Llama Stack abstractions matter.
- ✓ Switch to a non-thinking model (`qwen25-7b-instruct`, etc.).

**How to detect again:** Output starts with `<think>` and the actual response is much shorter than the consumed token count.

---

## 22. Inline Milvus stores RAG data ephemerally inside the llama-stack pod

**Symptom:** Vector stores and uploaded documents disappear after a llama-stack pod restart. RAG queries return zero hits.

**Root cause:** The `helm/llama-stack` chart defaults to `milvus.mode: inline`, which configures an embedded Milvus backed by a SQLite file at `/opt/app-root/src/.llama/distributions/rh/milvus.db`. There is no PVC; the file lives on the pod's writable layer and is wiped on every restart.

**Fix:** For persistence, deploy the standalone Milvus chart (`helm/milvus/`) and switch llama-stack to remote mode:
```bash
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.<ns>.svc:19530" \
  --set milvus.token="root:Milvus"
```

**How to detect again:** `curl /v1/providers | jq '.[] | select(.api=="vector_io")'` — if `provider_type` is `inline::milvus`, data is ephemeral. `remote::milvus` is the persistent mode.

---

## 23. `language_detection` shield mis-classifies short English greetings as non-English

**Symptom:** Sending `hi` or `hey, how are you` triggers `language_detection blocked input: ... (confidence: 0.91-0.98)`. The same shield works fine on full sentences.

**Root cause:** The detector model (`papluca/xlm-roberta-base-language-detection`) is brittle on very short text. Two- to four-word inputs are commonly mis-classified as Hindi, Hausa, Tagalog, etc. with high confidence.

**Why it "worked" in the genaiops playground:** Genaiops only invokes shields in **Agent-based mode**. The default mode is **Direct**, which calls the LLM with no shield wrapping. Even in Agent mode, the agent runtime wraps the user message in a longer system+context preamble before passing it to the safety call, so the detector sees a multi-sentence input and classifies it correctly.

Our `llama-stack-ui` runs `/v1/safety/run-shield` directly on the raw user message — short greetings hit the detector unwrapped and are blocked.

**Fix options:**
1. Drop `language_detection` from `input_shields`/`output_shields` in the Settings page — recommended if you support multilingual users anyway.
2. Raise the shield's `confidence_threshold` (in `helm/llama-stack/values.yaml` under `guardrails.language_detection.confidence_threshold`) from `0.85` to `0.99`.
3. Add a min-length skip in `chat.py` to bypass the shield for messages under N words.
4. Apply the shield only to the LLM output (not user input) — the LLM tends to produce longer responses where the detector is more reliable.

**How to detect again:** Shield blocks a clearly English message at ≥0.9 confidence. Confirm by sending a longer English sentence — if that passes, the issue is the detector's short-text reliability, not a real violation.

---

## 24. `helm upgrade --reuse-values` carries forward stale `vllm.url` / `vllm.apiToken` / `vllm.modelId`

**Symptom:** After someone swaps the running InferenceService model in the cluster (e.g. stops Qwen3, starts Qwen2.5), `helm upgrade --reuse-values` keeps the old URL/token/modelId. Llama Stack returns `APIConnectionError` (DNS) or `404 model not found`.

**Root cause:** `--reuse-values` is a footgun whenever any subset of values is environment-specific. It does exactly what it says — reuses the prior values literally — so cluster-state changes outside of helm's view (model swap, SA token rotation) silently desync.

**Fix:** Always re-source the cluster-truth values on every helm upgrade:
```bash
TOKEN=$(oc get secret -n <ns> default-token-<isvc>-sa -o jsonpath='{.data.token}' | base64 -d)
helm upgrade llama-stack helm/llama-stack/ -n <ns> --reuse-values \
  --set vllm.url="https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="<isvc>"
```

The `default-token-<isvc>-sa` secret is reproducible from the InferenceService name, so this is fully scriptable.

**How to detect again:** `helm get values llama-stack -n <ns> | grep -E 'url|modelId'` — if the URL or modelId reference an InferenceService that no longer exists (or is `Stopped`), this is the issue.
