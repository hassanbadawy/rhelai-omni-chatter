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

## 7. `embedding_dimension` mismatch on vector store creation

**Symptom:** Vector store creation fails or embeddings don't match when searching.

**Root cause:** The embedding dimension must match the model's actual output dimension. The Settings page reads `embedding_dimension` from the model's metadata, but if the user edits `config.yaml` manually or the metadata is missing, the stored dimension may be wrong.

**Fix:** Always select the embedding model via the Settings UI rather than editing `config.yaml` directly. The selectbox derives dimension from live model metadata.
