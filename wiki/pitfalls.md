# Pitfalls Log

---

## 36. `ogx-ui` chart hardcoded the build namespace in `image.repository` → `ErrImagePull: authentication required`

*Observed 2026-09-14, namespace `genai`, cluster `cluster-sznd8.sznd8.sandbox4020.opentlc.com`.*

**Symptom:** The `ogx-ui` pod never starts:

```
Back-off pulling image "image-registry.openshift-image-registry.svc:5000/agentic-ivr/ogx-ui:latest":
ErrImagePull: ... reading manifest latest in image-registry.openshift-image-registry.svc:5000/agentic-ivr/ogx-ui:
authentication required
```

**Root cause:** two things, in this order.

1. `helm/ogx-ui/values.yaml` shipped `image.repository` with a *literal* namespace baked in
   (`.../agentic-ivr/ogx-ui`) — a leftover from whichever namespace the image was last built in.
   The release was installed into `genai`, so the deployment pointed at a namespace that does not
   exist on this cluster (`oc get ns | grep agentic` → nothing).
2. No image had ever been built in `genai` — `oc get is,bc -n genai | grep ogx` was empty.

**"authentication required" is misleading.** The OpenShift internal registry returns
`authentication required` (not `404 manifest unknown`) for a repository that does not exist, because
it refuses to confirm or deny existence to a caller without pull rights on it. Read it as
**"repo/tag not found, or the puller has no rights on that namespace"** — check the imagestream
exists *in the namespace the repository string names* before chasing pull secrets or RBAC.

**Fix (cluster side):** build in the release namespace, then repoint the release.

```bash
NS=genai
oc new-build --binary --strategy=docker --name=ogx-ui -n $NS
oc patch bc/ogx-ui -n $NS --type=json \
  -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]'
oc start-build ogx-ui --from-dir=./ogx-ui --follow -n $NS
helm upgrade ogx-ui helm/ogx-ui/ -n $NS --reuse-values \
  --set image.repository="image-registry.openshift-image-registry.svc:5000/$NS/ogx-ui"
```

**Fix (chart side, v2.0.1):** the default is now namespace-aware and rendered through `tpl`, so a
plain `helm install` into any namespace resolves to that namespace's imagestream:

```yaml
# helm/ogx-ui/values.yaml
image:
  repository: "image-registry.openshift-image-registry.svc:5000/{{ .Release.Namespace }}/ogx-ui"
```
```yaml
# helm/ogx-ui/templates/deployment.yaml
image: "{{ tpl .Values.image.repository . }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
```

`tpl` is a no-op for a plain string, so `--set image.repository=quay.io/...` still works unchanged.

**Note on `--reuse-values`:** the bad value was carried in the release, not just in the chart file.
Bumping the chart default alone would not have fixed an existing release upgraded with
`--reuse-values` — the explicit `--set` above is required once. Same class of trap as the
`vllm.url` / `vllm.apiToken` staleness documented in [`runbook.md`](runbook.md).

**Files:** [`helm/ogx-ui/values.yaml`](../helm/ogx-ui/values.yaml),
[`helm/ogx-ui/templates/deployment.yaml`](../helm/ogx-ui/templates/deployment.yaml),
[`helm/ogx-ui/Chart.yaml`](../helm/ogx-ui/Chart.yaml) (2.0.0 → 2.0.1).

**Cross-refs:** [`components.md`](components.md) `helm/ogx-ui`, [`runbook.md`](runbook.md) build recipe.

---

## 35. LlamaStack 0.7.x — `vector_stores.default_embedding_model.model_id` must equal `provider_model_id`

**Symptom:** `CrashLoopBackOff` with: `Embedding model 'sentence-transformers/granite-embedding-125m' not found. Available: ['sentence-transformers/ibm-granite/granite-embedding-125m-english']`

**Root cause:** In 0.7.x, `vector_stores.default_embedding_model.model_id` is looked up as `{provider_id}/{model_id}` in the model registry. The registered key is `{provider_id}/{provider_model_id}`. When `model_id ≠ provider_model_id`, the lookup fails at startup with the above error.

**Fix:** Set `model_id` in `registered_resources.models[embedding]` to the same value as `provider_model_id`. Both must be the full HuggingFace path (e.g. `ibm-granite/granite-embedding-125m-english`). Also update `vector_stores.default_embedding_model.model_id` to match.

```yaml
vector_stores:
  default_embedding_model:
    provider_id: sentence-transformers
    model_id: ibm-granite/granite-embedding-125m-english  # must match provider_model_id below

registered_resources:
  models:
  - provider_id: sentence-transformers
    model_id: ibm-granite/granite-embedding-125m-english     # same as provider_model_id
    provider_model_id: ibm-granite/granite-embedding-125m-english
    model_type: embedding
```

**Files:** `helm/llama-stack/templates/llama-stack.yaml`, `helm/llama-stack/values.yaml` (`embedding.providerModelId`).

---

## 34. LlamaStack 0.7.x — `API 'agents' does not exist`

**Symptom:** `CrashLoopBackOff` with: `ValueError: API 'agents' does not exist`

**Root cause:** The `agents` API was replaced by the `responses` API in LlamaStack 0.7.x. The `rh-dev` distribution image bundled with RHOAI 3.4 no longer exports the `agents` router.

**Fix:** Replace `agents` with `responses` in the `apis` list. Replace the `inline::meta-reference` agents provider with the `inline::builtin` responses provider:

```yaml
apis: [responses, datasetio, files, inference, safety, scoring, tool_runtime, vector_io]

providers:
  responses:
  - provider_id: builtin
    provider_type: inline::builtin
    config:
      persistence:
        agent_state: {backend: kv_default, namespace: agents}
        responses: {backend: sql_default, table_name: responses}
```

---

## 33. LlamaStack 0.7.x — `Provider 'inline::meta-reference' not available for Api.eval`

**Symptom:** `CrashLoopBackOff` with: `ValueError: Provider 'inline::meta-reference' not available for Api.eval`

**Root cause:** The `inline::meta-reference` provider for `eval` was removed from the standard `rh-dev` distribution image in 0.7.x.

**Fix:** Set `eval: []` (empty list). Evaluation is now handled by external tools (MLflow, Eval Hub).

---

## 32. LlamaStack 0.7.x — `remote::trusty_fms` not available

**Symptom:** `CrashLoopBackOff` with: `ValueError: Provider 'remote::trusty_fms' not available` or safety-related startup failure.

**Root cause:** The `trusty_fms` safety provider is only available in the custom guardrails image (`quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms`), not in the standard `rh-dev` distribution.

**Fix:** Set `safety: []` (empty list). If guardrails are needed, use the custom image and the guardrails Helm values branch.

---

## 31. LlamaStack 0.7.x — `rag-runtime` provider replaced by `file-search`

**Symptom:** `CrashLoopBackOff` with: provider not found error for `inline::rag-runtime`.

**Root cause:** The `rag-runtime` tool_runtime provider was renamed to `file-search` in 0.7.x.

**Fix:** Replace in `tool_runtime` section:
```yaml
# OLD (0.3.x)
- provider_id: rag-runtime
  provider_type: inline::rag-runtime

# NEW (0.7.x)
- provider_id: file-search
  provider_type: inline::file-search
```

---

## 30. LlamaStack 0.7.x — `tls_verify: "false"` (string) parsed as file path

**Symptom:** vLLM provider fails TLS; error mentions trying to open `"false"` as a certificate file.

**Root cause:** In 0.7.x, `tls_verify` must be an unquoted YAML boolean (`false`). A quoted string `"false"` is interpreted as a file path by the Pydantic validator.

**Fix:** Use unquoted `false` in the config YAML:
```yaml
providers:
  inference:
  - provider_id: vllm
    provider_type: remote::vllm
    config:
      tls_verify: false    # NOT "false"
```

In Helm templates, use `{{ .Values.vllm.tlsVerify }}` where `tlsVerify` is stored as a quoted string in values.yaml but renders unquoted in the config (Helm renders `"false"` → `false` in the YAML output). Verify with `helm template`.

---

## 29. AutoRAG "Failed to load vector I/O providers" — three-layer root cause

**Symptom:** RHOAI Gen AI Studio AutoRAG page shows "Failed to load vector I/O providers. Check that the secret for the provided Llama Stack connection is valid and the API key has not expired."

**Root cause:** Three independent issues can cause this error (check in order):

**Layer 1 — Wrong RHOAI namespace selected.** The BFF passes the dashboard's active project as `namespace=` on all LSD calls. If the user has any project other than the one containing LlamaStack selected in the dashboard (e.g. `cert-manager`, `default`), the BFF searches the wrong namespace and finds no LSD. Fix: switch to the correct namespace in the RHOAI project selector before navigating to Gen AI Studio.

**Layer 2 — Missing `gen-ai-aa-vector-stores` ConfigMap.** The AutoRAG BFF serves the "Vector I/O provider" dropdown from this ConfigMap exclusively — it does NOT fall back to LlamaStack's own `/v1/vector_stores`. If the ConfigMap is absent, the dropdown is empty. Create it in the same namespace as LlamaStack:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gen-ai-aa-vector-stores
  namespace: <namespace>
data:
  config.yaml: |
    providers:
      vector_io:
        - provider_id: milvus
          provider_type: remote::milvus
          config:
            uri: http://milvus:19530
            custom_gen_ai:
              credentials:
                secretRefs:
                  - name: milvus-secret
                    key: root-password
    registered_resources:
      vector_stores:
        - provider_id: milvus
          vector_store_id: <vs_id_from_cluster>   # get from: oc exec ... curl /v1/vector_stores
          embedding_model: ibm-granite/granite-embedding-125m-english
          embedding_dimension: 768
          vector_store_name: "Milvus (<namespace>)"
```

The `vector_store_id` is auto-created by LlamaStack on first connection to Milvus. Get it with:
```bash
oc exec -n <ns> deploy/<lsd-name> -- curl -s http://localhost:8321/v1/vector_stores | jq -r '.data[0].identifier'
```

**Layer 3 — Short service name in `llama-stack-connection` secret.** The `gen-ai-ui` BFF container does not have the target namespace in its DNS search path. A short service name like `http://llama-stack-service:8321` results in HTTP 000 (silent DNS failure). Always use FQDN:
```
http://<service-name>.<namespace>.svc.cluster.local:8321
```

**Note:** LlamaStack 0.7.x has no API key authentication. `LLAMA_STACK_CLIENT_API_KEY: "unused"` is a valid placeholder — the server ignores all Bearer tokens.

**Files:** `helm/llama-stack/templates/llama-stack.yaml` (connection secret + gen-ai-aa-vector-stores ConfigMap), `helm/llama-stack/values.yaml` (`autorag.*`).

**Cross-refs:** See also pitfalls #35 (embedding model_id), #34 (agents API removed).

---

## 28. LiteMaaS: `kube:admin` has no `metadata.uid` — `oauth_id` NOT NULL violation on first login

**Symptom:** `{"error":{"code":"VALIDATION_ERROR","message":"Authentication failed"}}` on the OAuth callback. Backend log shows: `null value in column "oauth_id" of relation "users" violates not-null constraint`. OAuth code exchange itself succeeds; the crash happens when inserting the user row.

**Root cause:** OpenShift's `kube:admin` is a virtual user with no real `metadata.uid` (it comes back `null` from the users API). The backend maps `sub: userResponse.metadata.uid` to the `oauth_id` DB column which is `NOT NULL`. First login hits the constraint and aborts; subsequent retries get `unauthorized_client` because the OAuth code was already consumed.

**Fix:** The `patch-oauth-service` initContainer in `helm/litemaas/templates/backend-deployment.yaml` patches the compiled `oauth.service.js` at pod start to use `userResponse.metadata.uid || userResponse.metadata.name` as the `sub` value. For `kube:admin` this resolves to `"kube:admin"` instead of `null`.

**Silent failure risk (fixed 2026-06-29):** The original initContainer script had no `set -e` and no verification — if sed couldn't find the pattern (e.g. after a backend image update), it silently did nothing and the pod started with the unpatched file. The script now runs `set -e`, checks the pattern exists with `grep -q` before patching, and exits 1 if not found — so a broken patch surfaces as a pod `Init:Error` rather than a confusing auth failure at login time.

**How to detect a broken patch:** If the initContainer shows `Init:Error` or `Init:CrashLoopBackOff`, check its logs: `oc logs <pod> -c patch-oauth-service`. The error message will tell you the pattern was not found and which file to update.

**Files:** [`helm/litemaas/templates/backend-deployment.yaml`](../helm/litemaas/templates/backend-deployment.yaml) — `patch-oauth-service` initContainer.

**Cross-refs:** [`decisions.md`](decisions.md) (OpenShift SA OAuth mode), [`components.md`](components.md) (LiteMaaS).

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

**Fix:** Both `helm/llama-stack-playground/values.yaml` and `helm/ogx-ui/values.yaml` default `llamaStackUrl` / `ui.llamaStackUrl` to `http://llama-stack-service:8321`.

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

## 36. Renaming a MachineSet without renaming its selector labels makes it adopt the original worker Machines

**Symptom:** You copy an existing worker MachineSet with `oc get machineset -o yaml`, change `metadata.name` to something like `cluster-gpu-worker-us-east-2c`, and apply it. Two MachineSets now claim the same Machines; the controller scales and deletes nodes you didn't expect to touch.

**Root cause:** `metadata.name` is only one of *three* places the machineset identity appears. The other two still point at the source MachineSet:

- `spec.selector.matchLabels["machine.openshift.io/cluster-api-machineset"]`
- `spec.template.metadata.labels["machine.openshift.io/cluster-api-machineset"]`

A MachineSet owns whatever its selector matches. Leaving the selector on `<infra>-worker-<az>` means the new MachineSet's selector matches the *existing* worker Machines, and both controllers fight over them.

**Fix:** Rename all three together. Keep the `<infraID>-` prefix so the name still matches cluster convention:
```bash
sed -i '' 's/<infra>-worker-us-east-2c/<infra>-gpu-us-east-2c/g' machineset.yaml
# then verify exactly 2 label occurrences + 1 metadata.name
grep -c 'cluster-api-machineset: <infra>-gpu-us-east-2c' machineset.yaml   # must be 2
```

**How to detect again:** Before applying any derived MachineSet:
```bash
oc get machineset <new> -n openshift-machine-api \
  -o jsonpath='{.metadata.name}{"\n"}{.spec.selector.matchLabels.machine\.openshift\.io/cluster-api-machineset}{"\n"}'
```
The two lines must be identical. If they differ, do not apply.

---

## 37. `oc get machineset -o yaml` output is not re-appliable as-is

**Symptom:** Applying a MachineSet exported from a live cluster either errors on `resourceVersion` conflicts or silently carries stale autoscaler capacity hints.

**Root cause:** `oc get -o yaml` emits server-owned fields. These must all be stripped before re-apply:

| Field | Why it must go |
|---|---|
| `status:` | Subresource, server-owned |
| `metadata.managedFields` | Server-side-apply bookkeeping, huge and meaningless in a manifest |
| `metadata.resourceVersion` | Causes conflict errors on apply |
| `metadata.uid`, `creationTimestamp`, `generation` | Identity of the *old* object |
| `metadata.annotations["machine.openshift.io/GPU"]`, `.../vCPU`, `.../memoryMb` | Written by machine-controller-manager from the *source* instance type — stale and misleading after an instanceType change. The controller repopulates them. |

The GPU/vCPU/memoryMb annotations are the sneaky ones: a MachineSet with `instanceType: p5.4xlarge` carrying a stale `machine.openshift.io/GPU: '0'` will mislead the cluster-autoscaler about the node's capacity.

**Fix:** Strip all of the above. Keep `spec`, `metadata.name`, `metadata.namespace`, `metadata.labels`.

**How to detect again:** `grep -E 'managedFields|resourceVersion|uid:|^status:' machineset.yaml` must return nothing.

---

## 38. `InsufficientInstanceCapacity` leaves Machines in `Provisioning` forever, and the suggested AZs are boilerplate

**Symptom:** MachineSet reports `DESIRED 2 / CURRENT 2 / READY 0`. Machines sit in `Provisioning` indefinitely with empty `TYPE`, `ZONE`, and `PROVIDERID`. No node joins, and the phase never becomes `Failed`.

**Root cause:** The AWS machine controller retries `RunInstances` every ~3s forever on a capacity error. There is no terminal failure state and no backoff ceiling, so the MachineSet looks "in progress" indefinitely rather than erroring out. `oc get machines` alone tells you nothing — the reason is only in events.

The error text is actively misleading:
```
InsufficientInstanceCapacity: We currently do not have sufficient p5.4xlarge
capacity in the Availability Zone you requested (us-east-2c). ... You can
currently get p5.4xlarge capacity by ... choosing us-east-2a, us-east-2b.
```
Requesting `us-east-2b` then returns the identical error suggesting `us-east-2a, us-east-2c`. **The suggestion list is simply the complement of the AZ you asked for** — it is not a capacity signal. Do not burn time chasing zones on the strength of it.

**Fix / triage:** Read the actual reason, and distinguish capacity from quota:
```bash
oc get events -n openshift-machine-api --field-selector reason=FailedCreate \
  -o jsonpath='{range .items[*]}{.lastTimestamp}{" | "}{.message}{"\n"}{end}' | tail -3
```
| Error code | Meaning | Action |
|---|---|---|
| `InsufficientInstanceCapacity` | AWS has no hardware | Nothing you can do; needs a Capacity Reservation / Capacity Blocks for ML, or a different instance family |
| `VcpuLimitExceeded` | Account service quota | Raise the quota via AWS support |
| `Unsupported` | Type not offered in that AZ | Move AZ (this one *is* a real zone signal) |

Also note `replicas: N` is **not** atomic — each Machine gets its own independent `RunInstances` call, so a partially-available capacity pool will fill some replicas and keep retrying the rest. Scaling down to improve "odds" does nothing.

**How to detect again:** Any Machine in `Provisioning` with no `PROVIDERID` after ~2 minutes is not provisioning — check events immediately.

---

## 39. MIG is not available on any G-family AWS GPU instance

**Symptom:** You plan a GPU-as-a-Service setup with MIG partitioning, hit no capacity on P-family instances, and "fall back" to a cheaper `g5`/`g6` instance. MIG then cannot be enabled at all — the NVIDIA GPU Operator won't expose `nvidia.com/mig-*` resources and `nvidia-smi mig -lgip` reports the GPU does not support MIG.

**Root cause:** MIG requires a **data-center GPU of Ampere generation or newer**: A100, A30, H100, H200, B200. It is a hardware feature, not a driver setting. The GPUs in AWS's cheap GPU instances are all excluded:

| AWS instance | GPU | MIG? |
|---|---|---|
| `g4dn.*` | T4 (Turing) | No |
| `g5.*` | A10G (Ampere, but not data-center SKU) | **No** |
| `g6.*` | L4 (Ada) | **No** |
| `g6e.*` | L40S (Ada) | **No** |
| `p4d.24xlarge` | 8× A100 40GB | Yes — 56 slices |
| `p4de.24xlarge` | 8× A100 80GB | Yes — 56 slices |
| `p5.4xlarge` | 1× H100 80GB | Yes — 7 slices |
| `p5.48xlarge` | 8× H100 80GB | Yes — 56 slices |

A10G and L4 are Ampere/Ada silicon, which makes the "Ampere or newer" phrasing dangerously easy to misread — generation alone is not sufficient, it must be a data-center SKU.

**Consequence:** If the requirement is MIG, the *only* AWS options are P-family. `p5.4xlarge` (~$6.88/hr) is the cheapest MIG-capable instance AWS sells; `p4d.24xlarge` (~$21.96/hr, A100) is the usual fallback because a generation-older GPU has far better capacity availability.

**How to detect again:** Before choosing any GPU instance type for a MIG workload, check the GPU model against NVIDIA's supported list — <https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html>. Never substitute a G-family instance into a MIG plan on cost grounds.

---

## 40. Editing a MachineSet's template does NOT change existing Machines

**Symptom:** You patch a MachineSet's `instanceType`, `availabilityZone`, or subnet to work around a provisioning failure, wait, and see the *identical* error still naming the old value. It looks like the patch was ignored.

**Root cause:** A MachineSet is not a Deployment — it has **no rollout controller**. `spec.template` is only a stamp used when creating *new* Machines. Existing Machine objects carry their own frozen copy of `spec.providerSpec`, and nothing ever reconciles them back toward the template.

So a Machine stuck retrying `RunInstances` keeps retrying with its **original** spec forever, no matter how many times you patch the parent MachineSet. Observed directly:

```
MachineSet template AZ: us-east-2c     # patched
Machine  ...-kvcxt AZ:  us-east-2b     # still launching here
Machine  ...-xm8sm AZ:  us-east-2b     # still launching here
```

**Fix:** Delete the Machines so the MachineSet recreates them from the new template. Safe when no EC2 instance was ever created (nothing to destroy):

```bash
oc patch machineset <name> -n openshift-machine-api --type=merge -p '{...}'
oc delete machine -n openshift-machine-api \
  -l machine.openshift.io/cluster-api-machineset=<name>
```

For Machines that *do* back a running node, scale down / cordon+drain instead of deleting blindly.

**How to detect again:** After any MachineSet patch, compare template against the actual Machines — never trust the template alone:
```bash
oc get machineset <name> -n openshift-machine-api \
  -o jsonpath='{.spec.template.spec.providerSpec.value.placement.availabilityZone}{"\n"}'
for m in $(oc get machines -n openshift-machine-api -o name | grep <name>); do
  oc get $m -o jsonpath='{.metadata.name}{" "}{.spec.providerSpec.value.placement.availabilityZone}{"\n"}'
done
```
If they disagree, your patch is not being tested.

---

## 41. Unknown `OdhDashboardConfig` fields are pruned with a warning, so the feature silently never turns on

**Symptom:** You add dashboard feature flags, apply, and get an admission *warning* (not an error):
```
OdhDashboardConfig odh-dashboard-config violates policy 299 -
  "unknown field \"spec.dashboardConfig.Gpuaas\"",
  "unknown field \"spec.dashboardConfig.Guardrails\"",
  "unknown field \"spec.dashboardConfig.aiAssetCustomEndpoints.externalProviders\""
```
The resource applies "successfully" and the features stay off.

**Root cause:** This is API-server field pruning, not a rejection. Unknown fields are stripped before persistence, so the CR is stored *without* them. Nothing fails and nothing retries — the setting simply never existed. Three distinct causes produced the warning above:

1. **Case sensitivity.** CRD field names are lowercase; YAML keys are case-sensitive. `Gpuaas` ≠ `gpuaas`, `Guardrails` ≠ `guardrails`, `Mlflow` ≠ `mlflow`.
2. **Dots in YAML keys are not paths.** `aiAssetCustomEndpoints.externalProviders: true` does not mean "nested field" — it creates one literal key with a dot in its name.
3. **Same name, two different fields.** `spec.dashboardConfig.aiAssetCustomEndpoints` is a **boolean** (turn feature on); `spec.genAiStudioConfig.aiAssetCustomEndpoints` is an **object** holding `externalProviders` and `clusterDomains` (configure it). Both are required — the boolean alone does nothing for external providers.

**Fix:** Validate every key against the **live CRD**, which is authoritative and version-specific — the docs page lags and its true/false phrasing is ambiguous:
```bash
oc get crd odhdashboardconfigs.opendatahub.io \
  -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema.properties.spec.properties.dashboardConfig.properties}' \
  | python3 -c 'import json,sys; [print(k) for k in sorted(json.load(sys.stdin))]'
```
Descriptions and deprecations live there too — e.g. `mlflow` is marked *"DEPRECATED: MLflow is now always enabled when the operator component is present."*

**Semantics** (confirmed from CRD descriptions, RHOAI 3.5.0):

| Field shape | `true` means |
|---|---|
| `disableX` | feature **off** |
| plain feature flag (`gpuaas`, `guardrails`, `genAiStudio`, …) | feature **on** |

The docs sentence "to show features set the value to `false`" applies **only to the `disable*` family** — applying it to `gpuaas` inverts your intent.

**How to detect again:** Never trust a clean apply. Read the field back — a pruned field returns empty:
```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.gpuaas}{"\n"}'
```
Empty output = pruned, feature off. Treat any `violates policy 299 - "unknown field ..."` warning as a hard failure.

---

## 42. RHOAI 3.5.0 cannot enable Models-as-a-Service — both paths are blocked

**Symptom:** Following the official MaaS guide on RHOAI 3.5.0, `maas-api` never deploys and `redhat-ai-gateway-infra` stays empty, even with `aigateway.modelsAsAService: Managed` in the DSC.

**Root cause:** 3.5.0 deprecated the 3.4-era wiring *and* ships without its replacement, leaving no working path:

1. **Legacy path blocked by CEL.** The docs ([3.4](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service_maas)) say `spec.components.kserve.modelsAsService.managementState: Managed`. On 3.5.0:
   ```
   modelsAsService is deprecated; cannot re-enable once Removed.
   Use spec.components.aigateway.modelsAsAService instead
   ```
   The CRD description spells out the rule: *"One-directional CEL: Managed→Removed (cleanup) is allowed; Removed→Managed is blocked."* A cluster **upgraded** from 3.4 with it already `Managed` keeps working; a fresh 3.5.0 install can never turn it on.

2. **New path has no CRD.** Setting `aigateway.managementState: Managed` yields:
   ```
   AIGatewayReady = False | NotReady: Failed to get module status:
     no matches for kind "AIGateway" in version "components.platform.opendatahub.io/v1alpha1"
   ```
   This is not a broken install — the catalog bundle never had it:
   ```bash
   oc get packagemanifest rhods-operator -n openshift-marketplace -o json | python3 -c "
   import json,sys
   d=json.load(sys.stdin)
   for ch in d['status']['channels']:
       if ch['name']=='stable-3.x':
           print([c['kind'] for c in ch['currentCSVDesc']['customresourcedefinitions']['owned']])"
   ```
   Returns 16 kinds (Auth, DataScienceCluster, GatewayConfig, Kueue, Trainer, TrustyAI, …) with **no AIGateway**, while all 14 sibling component CRDs are installed.

3. **Dashboard flag also deprecated.** `maasAuthPolicies`, required by the 3.4 docs, is rejected: *"DEPRECATED: spec.dashboardConfig.maasAuthPolicies must be removed or left unchanged."*

Confirming signal: the **3.5 MaaS doc page 404s** — it exists only for 3.3 and 3.4.

**The trap:** `spec.components.aigateway` has *three* independent fields — `managementState` (the module), `modelsAsAService`, and `batchGateway`. Setting only the submodule leaves the parent unset, which **defaults to `Removed`**, so the whole module is off and the condition reads `Module ManagementState is set to Removed`. That misleads you into thinking the submodule value is wrong, when the real problem is one level up — and fixing it only surfaces the missing CRD.

**Fix:** None on 3.5.0. Use an RHOAI build that ships the AI Gateway component, or a 3.4 cluster where the kserve path is still permitted. Everything else (GatewayClass, `maas-default-gateway`, RHCL, PostgreSQL, UWM) can be fully prepared in advance and is not the blocker.

**How to detect again:** Before following any MaaS guide, check the component CRD exists — one command, saves hours:
```bash
oc get crd aigateways.components.platform.opendatahub.io
```
`NotFound` means MaaS cannot be enabled on that cluster regardless of DSC settings.

**Caution:** patching `aigateway.managementState: Managed` when the CRD is absent flips the whole DSC to `Ready=False / Some modules are not ready: aigateway`. Revert by removing the key (not by setting it to `Removed`, which is not the original state):
```bash
oc patch $(oc get dsc -o name|head -1) --type=json \
  -p '[{"op":"remove","path":"/spec/components/aigateway/managementState"}]'
```

---

## 43. A Gateway with a `*.apps` wildcard hostname hijacks the cluster's wildcard DNS and takes down every route

**Symptom:** After creating a Gateway, unrelated cluster URLs break — the OpenShift console, the RHOAI dashboard, everything on `*.apps` — returning HTTP 404 from an unexpected load balancer. Later, after "fixing" the Gateway, those hostnames stop resolving at all.

**Root cause:** **Every OpenShift Gateway publishes its own `DNSRecord`.** Creating a Gateway whose listener hostname is `*.apps.<cluster-domain>` publishes a Route53 CNAME for that exact name — which is the name the ingress operator's `default-wildcard` record already owns. The Gateway's record **overwrites** it, so all `*.apps` traffic is sent to the new Gateway's ELB, which 404s anything it has no HTTPRoute for.

The second failure is worse. Narrowing the Gateway hostname afterwards deletes the colliding record, and because both records shared one zone entry, the wildcard CNAME is removed **entirely** — `*.apps` then resolves to nothing. The ingress operator's CR still reports `Published=True ProviderSuccess`, so the status lies; only a live DNS query reveals it.

Diagnosis — compare what the hostname resolves to against the Gateway ELBs:
```bash
dig +short rh-ai.apps.<cluster-domain>                      # hijacked hostname
dig +short <gateway-elb>.us-east-2.elb.amazonaws.com        # the offending Gateway
oc get svc router-default -n openshift-ingress \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'  # the correct target
oc get dnsrecord -A     # one "<gateway>-wildcard" record per Gateway
```
If the hostname's IPs match a Gateway's ELB instead of `router-default`'s, that Gateway has hijacked it.

**Fix:**
1. Scope the Gateway listener to a specific hostname — never a wildcard:
   ```bash
   oc patch gateway <name> -n openshift-ingress --type=json \
     -p '[{"op":"replace","path":"/spec/listeners/0/hostname","value":"inference.apps.<cluster-domain>"}]'
   ```
2. Force the ingress operator to re-publish the wildcard it owns:
   ```bash
   oc delete dnsrecord default-wildcard -n openshift-ingress-operator
   ```
   The operator recreates it within seconds from `router-default`'s ELB.
3. Verify against a public resolver, **not** your local one:
   ```bash
   dig +short @8.8.8.8 console-openshift-console.apps.<cluster-domain>
   ```

**The outage outlives the fix.** While the record was missing, every resolver that
looked it up cached the NXDOMAIN. Per RFC 2308 the negative-cache lifetime is
`min(SOA TTL, SOA minimum)`; on these clusters that is `min(900, 86400)` = **15
minutes**. So browsers keep reporting `DNS_PROBE_POSSIBLE` for up to 15 minutes
*after* DNS is correct, which reads exactly like the fix failed. Check the SOA
before concluding anything is still broken:
```bash
dig +noall +authority @8.8.8.8 nonexistent.apps.<cluster-domain> SOA
```
Clear it with `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`, plus
`chrome://net-internals/#dns` → Clear host cache (Chrome caches separately from the
OS), or test from a phone on cellular to bypass every cache at once.

**How to detect again / prevent:** Before creating any Gateway, derive the hostname from what the consumer already publishes rather than inventing one. For an `LLMInferenceService`, `status.url` and `status.addresses` name it exactly:
```bash
oc get llminferenceservice <name> -n <ns> -o jsonpath='{.status.url}{"\n"}'
# https://inference.apps.<cluster-domain>/<ns>/<name>   -> hostname is inference.apps.<cluster-domain>
```
**Never put `*.apps.<cluster-domain>` on a Gateway listener.** Use `allowedRoutes.namespaces.from: All` if cross-namespace attachment is what you need — that is the knob for route scope; the hostname is not.

---

## 44. vLLM crash-loops when a model's default context exceeds the GPU's KV cache

**Symptom:** An `LLMInferenceService` pod sits in `CrashLoopBackOff` indefinitely (observed: 616 restarts over 2.5 days). The `main` container exits during engine startup with a generic tail:
```
RuntimeError: Engine core initialization failed. See root cause above.
```
The real cause is ~40 lines earlier and easy to miss:
```
ValueError: To serve at least one request with the model's max seq len (262144),
26.0 GiB KV cache is needed, which is larger than the available KV cache memory
(14.79 GiB). Based on the available memory, the estimated maximum model length
is 149104.
```

**Root cause:** vLLM sizes the KV cache for the model's *full advertised* context. Ministral-3B declares 262144 tokens; on a 24 GB A10G only ~14.79 GiB is left for KV after weights and CUDA graphs, so the engine refuses to start. Nothing about this is visible from `oc get pods` — only the previous container's log shows it.

**Fix:** Cap the context. Do **not** set `spec.template.containers[0].args` — the RHOAI serving template builds a long `vllm serve` command (served-model-name, TLS certs, version-conditional flags) and ends with `${VLLM_ADDITIONAL_ARGS} $@`, so args are the documented extension point:
```bash
oc patch llminferenceservice <name> -n <ns> --type=json \
  -p '[{"op":"add","path":"/spec/template/containers/0/env","value":[
        {"name":"VLLM_ADDITIONAL_ARGS","value":"--max-model-len 32768"}]}]'
```
Verify from inside the pod — `max_model_len` is reported per model:
```bash
oc exec -n <ns> <pod> -c main -- curl -sk https://localhost:8000/v1/models
```

**How to detect again:** Any GPU model stuck in `CrashLoopBackOff` — go straight to
`oc logs <pod> -c main --previous | grep -B2 ValueError`. The error names the largest
context that *would* fit, so pick a round number below it.

---

## 45. `LLMInferenceService` reports `RefsInvalid` because the KServe ingress Gateway does not exist

**Symptom:** A model deploys but never becomes Ready:
```
HTTPRoutesReady False | RefsInvalid: Managed HTTPRoute references non-existent
  Gateway openshift-ingress/openshift-ai-inference
```

**Root cause:** KServe points every managed HTTPRoute at whatever `inferenceservice-config` names, and nothing creates it:
```bash
oc get cm inferenceservice-config -n redhat-ods-applications \
  -o jsonpath='{.data.ingress}' | python3 -m json.tool | grep kserveIngressGateway
#   "kserveIngressGateway": "openshift-ingress/openshift-ai-inference"
```
The KServe component reports `Ready=True` and `AllResourcesApplied` while this Gateway is absent — it is expected to pre-exist, and its absence is only visible on the individual service.

**Fix:** Create the Gateway with the **exact hostname the service already publishes** — never a wildcard (see pitfall #32):
```bash
oc get llminferenceservice <name> -n <ns> -o jsonpath='{.status.url}{"\n"}'
# https://inference.apps.<domain>/<ns>/<name>  ->  hostname is inference.apps.<domain>
```
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata: {name: openshift-ai-inference, namespace: openshift-ingress}
spec:
  gatewayClassName: openshift-default
  listeners:
    - name: https
      hostname: inference.apps.<cluster-domain>   # specific, never *.apps
      port: 443
      protocol: HTTPS
      allowedRoutes: {namespaces: {from: All}}     # this is the cross-namespace knob
      tls:
        mode: Terminate
        certificateRefs: [{group: "", kind: Secret, name: cert-manager-ingress-cert}]
```
`HTTPRoutesReady` and `RouterReady` flip to True within seconds.

---

## 46. `oc get nemoguardrails` returns the wrong resource — two CRDs share the short name

**Symptom:** You create a `NemoGuardrails` CR, the pod runs fine, but:
```
$ oc get nemoguardrails -n <ns>
No resources found in <ns> namespace.
```

**Root cause:** Two CRDs claim that short name on a RHOAI 3.5 cluster:
```
nemoguardrails.apps.nvidia.com
nemoguardrails.trustyai.opendatahub.io
```
The bare name resolves to NVIDIA's, which has no instances, so the RHOAI resource looks like it failed to create when it is actually healthy.

**Fix:** Always fully qualify:
```bash
oc get nemoguardrails.trustyai.opendatahub.io -n <ns>
```

**How to detect again:** `oc get crd | grep nemoguardrails` — if two lines come back, every bare-name command is ambiguous. Applies to `describe`, `delete` and `patch` too.
