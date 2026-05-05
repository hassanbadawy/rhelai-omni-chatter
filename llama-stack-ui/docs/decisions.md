# Architectural Decisions

Each entry answers: what was chosen, what was the alternative, and why.

---

## 1. Chat Completions API instead of Responses API

**Chosen:** `POST /v1/chat/completions` for all chat interactions.

**Alternative:** `POST /v1/responses` (server-side stateful responses with `previous_response_id` chaining).

**Why:** The Responses API does not forward `max_tokens` to the underlying vLLM backend. The server injects its own `VLLM_MAX_TOKENS` default (e.g. 4096) regardless of what the client sends. This makes it impossible to control output length or prevent context overflow for small-context models. Chat Completions passes `max_tokens` through correctly.

**Side effect:** Conversation history must be managed client-side (see decision 2). The Responses API methods still exist in `api.py` (`create_response`, `list_responses`, `delete_response`, etc.) as dead code — kept in case the vLLM forwarding issue is fixed upstream.

---

## 2. Client-side conversation history (session state) instead of server-side

**Chosen:** `st.session_state.conversations[conv_id]` — a dict of `[{role, content}]` lists, keyed by UUID.

**Alternative:** Llama Stack Conversations API (`POST /v1/conversations`, `GET /v1/conversations/{id}/items`).

**Why:** Follows directly from decision 1. Since Chat Completions is stateless, the full message history must be sent with every request anyway. The Conversations API was not tested against the available server distributions (rh-dev). Client-side state is simpler and has no server dependency.

**Known limitation:** Messages are lost on page refresh. `conversations.json` only persists conversation *names* (display labels), not message content. If persistence across sessions is needed, revisit the Conversations API or add local serialization.

---

## 3. Context length probing via `max_tokens=999999`

**Chosen:** `get_model_context_length()` in `api.py` tries model metadata fields first (`max_seq_len`, `context_length`, `max_model_len`, etc.), then falls back to sending a request with `max_tokens=999999` and parsing the error message for the actual limit.

**Why:** The Llama Stack `/v1/models` metadata response for vLLM-backed models frequently omits all context length fields. The probe approach works because vLLM returns a descriptive error ("maximum context length is N tokens") when the requested output would overflow. A 200 response to the probe means the model has a large context and no cap is needed.

**Risk:** The probe sends a real request to the inference server on every new model selection (cached in session state after first call). If the server is slow or the model is busy, this adds latency to page load.

---

## 4. Raw `requests` instead of the `llama-stack-client` SDK

**Chosen:** Direct HTTP calls via the `requests` library in `modules/api.py`.

**Why:** The `llama-stack-client` Python SDK version must match the server version exactly, and the server version is controlled by the RHOAI operator. Using raw `requests` avoids version lock-in and gives full control over streaming SSE parsing and error handling.

---

## 5. UUID for conversation IDs

**Chosen:** `str(uuid.uuid4())` as the conversation key when a new chat is created.

**Alternative (previous):** The server-assigned response ID from the first Responses API call was used as the conversation key. This tied conversation identity to an ephemeral server object.

**Why:** After switching to Chat Completions (decision 1), there is no server-assigned ID. UUID generated client-side is stable, unique, and independent of server state.

---

## 6. `max_tokens` capped at `context_length / 2` per request

**Chosen:** `effective_max_tokens = min(configured_max_tokens, context_length // 2)`.

**Why:** Reserving half the context for input (conversation history + system prompt + RAG context) and half for output is a safe default. Without this cap, small-context models like `qwen25-vl-7b-instruct` (2024 tokens) will error on every request if `max_tokens` is set to e.g. 2000 with any non-trivial input.

**Related:** The oldest messages in the conversation are trimmed (starting after the system message) until the estimated input token count fits within `context_length - effective_max_tokens`.
