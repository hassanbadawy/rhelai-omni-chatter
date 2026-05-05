# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Llama Stack Playground — a Streamlit UI for interacting with the Llama Stack LLM platform. Supports chat with streaming, RAG (Retrieval-Augmented Generation), document/vector store management, and model configuration.

## Running the Application

```bash
# Local development
export LLAMA_STACK_API_ENDPOINT="https://your-endpoint"
streamlit run app.py

# Quick start script
./run.sh

# Docker build & run
docker build -f Containerfile -t llama-stack-playground .
./start-dev-container.sh                          # UI only (port 8501)
TOGETHER_API_KEY=<key> ./start-dev-container.sh --with-api  # UI + API server (port 8321)
```

No test suite exists in this repository.

## Architecture

- **`app.py`** — Entry point, sets up Streamlit page navigation (Chat, Documents, Settings)
- **`pages/chat.py`** — Chat interface using Chat Completions API with conversation history in session state
- **`pages/documents.py`** — Vector store ("case") creation, file upload, and search
- **`pages/settings.py`** — Endpoint, model selection, embedding model, vector IO provider, and sampling parameter configuration
- **`modules/api.py`** — Custom `LlamaStackClient` class using raw `requests` for all REST API calls; includes logging via Python `logging` module
- **`modules/config.py`** — YAML-based config loader/saver (`config.yaml`) and JSON-based conversation name storage (`conversations.json`)

### Data Flow

1. Config loaded from `config.yaml` on startup; defaults defined in `modules/config.py:DEFAULTS`
2. `modules/api.py` makes REST calls to Llama Stack backend (endpoint set in config — must be configured in Settings)
3. Chat uses **Chat Completions API** (`/v1/chat/completions`) with streaming SSE. Full message history (system prompt + conversation + new message) is sent with each request. Conversation history is stored in `st.session_state.conversations`
4. Conversation names are tracked locally in `conversations.json` keyed by `user_id` and a UUID conversation ID
5. On page load, model context length is queried from the server (metadata or probe) and cached in session state. `max_tokens` is capped to `context_length / 2` per request to prevent exceeding the model's limit
6. RAG: if a vector store is selected in the sidebar, top-5 chunks are retrieved and prepended to the user's prompt as context
7. Documents page manages vector stores via `/v1/vector_stores` and file uploads via `/v1/files` with chunking (512 tokens, 50 overlap)

## Key Conventions

- Python 3.10+ (3.12 in Docker via UBI9)
- Streamlit session state for all page-level state management
- REST API communication via raw `requests` (not the `llama-stack-client` library's built-in client)
- Configuration persisted as YAML in `config.yaml`
- Multi-language UI support (English, Arabic, French, Spanish, German, Chinese, Japanese, Korean, Portuguese, Russian, Turkish, Hindi)
- Error display via `st.error()` with try/except patterns
- Python `logging` module used in `chat.py` and `api.py` — logs appear in the terminal running streamlit
- All docs are in .md in ./docs dir, read them to understand more:
  - `docs/decisions.md` — *why* key architectural choices were made (Chat Completions vs Responses API, client-side history, context probing, etc.)
  - `docs/entanglements.md` — cross-file dependency map: session state keys, config.yaml consumers, api.py→chat.py contract, dead code inventory
  - `docs/pitfalls.md` — pitfall log with root cause and fix for every non-obvious bug hit so far
  - `docs/api-improvements.md` — future improvement opportunities across the Llama Stack API

## Wiki Rule

After any session that discovers a new pitfall, changes an architectural decision, or adds/removes a cross-file dependency — update the relevant `docs/` page before closing. Good findings don't disappear into chat history.

## Known Pitfalls

- **Responses API (`/v1/responses`) does not forward `max_tokens` to vLLM** — the server injects its own `VLLM_MAX_TOKENS` default (e.g. 4096) regardless of what the client sends. Use Chat Completions API (`/v1/chat/completions`) instead, which properly passes `max_tokens` through.
- **Streamlit selectbox stale session state** — when server-side options change (e.g. model list), `st.selectbox` can silently return a cached value that no longer exists in the options. Always use explicit `key` parameters and clear stale session state before rendering: `if key in st.session_state and st.session_state[key] not in options: del st.session_state[key]`
- **Small context models** — some models (e.g. qwen25-vl-7b-instruct) have very small context windows (2024 tokens). The code probes the server for context length via `get_model_context_length()` and caps `max_tokens` accordingly. If the metadata lookup fails, it sends a probe request with an intentionally large `max_tokens` and parses the context limit from the error message.
- **SSE stream errors** — the Llama Stack server can return errors as `{"error": {...}}` inside the SSE data stream (HTTP 200 status). Both `chat_completions_stream` and `_create_response_stream` detect this and raise `RuntimeError` so errors are not silently swallowed.
