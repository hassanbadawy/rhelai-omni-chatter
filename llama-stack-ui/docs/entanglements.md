# Code Entanglements

Cross-file dependencies that are not obvious from reading a single file.

---

## Session State Keys

All keys live in `st.session_state`. Owner = file that writes the key. Readers = files that read it.

| Key | Type | Owner | Readers | Notes |
|-----|------|-------|---------|-------|
| `conversations` | `dict[str, list[dict]]` | `chat.py` | `chat.py` | Full message history. Outer key = conv UUID. Value = `[{role, content}]`. Lost on page refresh. |
| `active_chat_key` | `str \| None` | `chat.py` | `chat.py` | UUID of the currently open conversation. `None` = new chat. |
| `pending_chat_name` | `str` | `chat.py` (rename flow) | `chat.py` (on first message) | Name pre-typed before first message in a new chat. Consumed and deleted when the conv is created. |
| `confirm_delete_conv` | `bool` | `chat.py` | `chat.py` | Controls visibility of the delete confirmation UI. |
| `show_rename` | `bool` | `chat.py` | `chat.py` | Controls visibility of the rename input. |
| `_ctx_len_{model_id}` | `int \| None` | `chat.py` | `chat.py` | Cached context length for a model. Populated by `api.get_model_context_length()` on first load. Key includes model ID so it invalidates when model changes. |
| `settings_model` | `str` | `settings.py` | `settings.py` | Streamlit widget key for model selectbox. Cleared explicitly if the cached value is no longer in the option list. |
| `settings_embedding` | `str` | `settings.py` | `settings.py` | Same pattern as `settings_model` for embedding model selectbox. |
| `settings_vio` | `str` | `settings.py` | `settings.py` | Same pattern for vector IO provider selectbox. |

---

## `config.yaml` Field Consumers

| Field | Written by | Read by | Notes |
|-------|-----------|---------|-------|
| `endpoint` | `settings.py` | `api.py` (`base_url` property, every request) | Every API call re-reads config via `load_config()`. No caching at the client level. Falls back to `LLAMA_STACK_API_ENDPOINT` env var when YAML value is empty/missing. |
| `model` | `settings.py` | `chat.py` | Falls back to first model from server if empty. Initial default sourced from `DEFAULT_MODEL` env var. |
| `embedding_model` | `settings.py` | `documents.py` (create vector store) | |
| `embedding_dimension` | `settings.py` | `documents.py` (create vector store) | Derived from the selected embedding model's metadata. |
| `vector_io_provider` | `settings.py` | `documents.py` (create vector store) | |
| `user_id` | `settings.py` | `chat.py`, `modules/config.py` | Keys the conversation name lookup in `conversations.json`. |
| `language` | `settings.py` | `chat.py` | Used in the document summary prompt template (`SUMMARY_PROMPT`). |
| `system_prompt` | `settings.py` | `chat.py` | Injected as the first message in every API call if non-empty. |
| `temperature` | `settings.py` | `chat.py` | Passed through to `chat_completions_stream`. |
| `top_p` | `settings.py` | `chat.py` | Passed through to `chat_completions_stream`. |
| `max_tokens` | `settings.py` | `chat.py` | Further capped by `context_length / 2` before use. |
| `safety_enabled` | `settings.py` | `chat.py` | Gates all shield checks. When false, input/output shield calls are skipped entirely. |
| `input_shields` | `settings.py` | `chat.py` | List of shield IDs run on user input before sending to LLM. Populated from `/v1/shields` multiselect. |
| `output_shields` | `settings.py` | `chat.py` | List of shield IDs run on LLM response before displaying. |

---

## Environment Variable Inputs

| Env var | Read by | Purpose |
|---------|---------|---------|
| `LLAMA_STACK_API_ENDPOINT` | `modules/config.py` (`load_config()`) | Default backend URL used when `config.yaml` does not specify `endpoint`. Set by the helm chart from `ui.llamaStackUrl`. |
| `DEFAULT_MODEL` | `modules/config.py` (`load_config()`) | Default model identifier used when `config.yaml` does not specify `model`. Set by the helm chart from `ui.defaultModel`. |
| `LLAMA_STACK_UI_DATA_DIR` | `modules/config.py` (module-level) | Overrides the directory where `config.yaml` and `conversations.json` are read/written. Defaults to the package directory if unset. The chart points it at `/tmp/llama-stack-ui-data` so the read-only baked YAML does not shadow env-supplied defaults. |

---

## `conversations.json` Structure

```json
{
  "<user_id>": {
    "<conv_uuid>": "<display name>"
  }
}
```

- This file stores **only names**, not message content.
- `user_id` comes from `config.yaml`.
- `conv_uuid` is a `uuid4()` string generated in `chat.py` when a new conversation is first committed.
- Message content lives exclusively in `st.session_state.conversations[conv_uuid]` and is lost on page refresh.
- A conversation is "valid" (shown in the sidebar) only if its UUID exists in **both** `conversations.json` and `st.session_state.conversations`. Keys in one but not the other are silently filtered out.

---

## `api.py` → `chat.py` Context Length Contract

`chat.py` calls `client.get_model_context_length(model_id)` once per model per session and caches the result in `st.session_state[f"_ctx_len_{model_id}"]`. The returned value (or `None`) then drives three downstream decisions in `chat.py`:

1. **`effective_max_tokens`** = `min(config_max_tokens, context_length // 2)`
2. **Message trimming** — oldest non-system messages are removed until estimated input fits in `context_length - effective_max_tokens`
3. **RAG context truncation** — `retrieval_output` is sliced to `(context_length * 3) // 2 - overhead - history_chars` characters

If `get_model_context_length()` returns `None` (metadata missing and probe inconclusive), all three of the above are skipped and configured values are used as-is.

---

## `get_vector_io_providers_from()` Return Format

Returns `list[{"provider_id": str, "provider_type": str}]` — **full dicts, not strings**. `settings.py` extracts `vio_ids = [p["provider_id"] for p in vector_io_providers]` for the selectbox options. The stale-state guard checks against `vio_ids` (strings), not the raw dict list.

## Dead Code in `api.py`

The following methods exist but are **not called by any current page**:

| Method | Originally used by |
|--------|--------------------|
| `create_response()` | `chat.py` (before switch to Chat Completions) |
| `_create_response_stream()` | Called by `create_response()` |
| `list_responses()` | `chat.py` (for loading conversation history from server) |
| `get_response()` | Not used even before the switch |
| `get_response_input_items()` | Not used even before the switch |
| `delete_response()` | `chat.py` (on conversation delete) |
| `version()` | Not wired to any UI yet |
| `guardrails_chat()` | Not wired — for direct Guardrails Gateway path (bypasses Llama Stack) |
| `check_external_detector()` / `run_external_detectors()` / `run_regex_filters()` | Not wired — for direct detector calls (bypasses orchestrator) |

The Responses API methods are kept intentionally — see `docs/decisions.md` decision 1.

**Active safety methods** (added in sync with remote, called by `chat.py`):
`run_shield()`, `get_shields()`, `get_shields_from()`, `register_shield()`, `get_safety_providers()`
