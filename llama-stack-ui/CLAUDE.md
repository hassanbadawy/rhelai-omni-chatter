# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Llama Stack Playground — a Streamlit UI for interacting with the Llama Stack LLM platform. Supports chat with streaming, RAG (Retrieval-Augmented Generation), document/vector store management, and model configuration. All development is in the `playground/` directory.

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

- **`app.py`** — Entry point, sets up Streamlit page navigation
- **`pages/chat.py`** — Chat interface with optional RAG retrieval from vector stores
- **`pages/documents.py`** — Vector store creation, file upload, and search
- **`pages/settings.py`** — Endpoint, model selection, and sampling parameter configuration
- **`modules/api.py`** — Wrapper around `LlamaStackClient` for all REST API calls (models, chat, vector stores, files, health)
- **`modules/config.py`** — YAML-based config loader/saver (`config.yaml`)

### Data Flow
1. Config loaded from `config.yaml` on startup
2. `modules/api.py` makes REST calls to Llama Stack backend (default `http://localhost:8321`)
3. Chat page streams responses via SSE (`data: {json}` format); if a vector store is selected, top-5 RAG chunks are prepended to the prompt
4. Documents page manages vector stores and file uploads with chunking (512 tokens, 50 overlap)

## Key Conventions

- Python 3.10+ (3.12 in Docker via UBI9)
- Streamlit session state for all page-level state management
- REST API communication via `llama-stack-client` library
- Configuration persisted as YAML in `config.yaml`
- Multi-language UI support (English, Arabic, French, Spanish, German, Chinese, Japanese, Korean, Portuguese, Russian, Turkish, Hindi)
- Error display via `st.error()` with try/except patterns
- All docs are in .md in ./docs dir, read them to understand more
