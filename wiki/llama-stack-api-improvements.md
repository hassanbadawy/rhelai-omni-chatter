# Llama Stack API — Playground Improvement Opportunities

## Current Coverage

The playground currently uses **13 endpoints** from the Llama Stack API:

| Endpoint | Used In |
|----------|---------|
| `GET /v1/health` | settings.py (test connection) |
| `GET /v1/models` | settings.py (model dropdowns), chat.py (fallback model) |
| `GET /v1/providers` | settings.py (vector_io provider dropdown) |
| `POST /v1/chat/completions` | chat.py (streaming chat + non-streaming case summary) |
| `GET /v1/vector_stores` | chat.py (RAG selector), documents.py (list cases) |
| `POST /v1/vector_stores` | documents.py (create case) |
| `DELETE /v1/vector_stores/{id}` | documents.py (delete case) |
| `POST /v1/files` | documents.py (upload) |
| `POST /v1/vector_stores/{id}/files` | documents.py (attach file) |
| `GET /v1/vector_stores/{id}/files` | documents.py (list files) |
| `POST /v1/vector_stores/{id}/search` | chat.py (RAG retrieval) |

**Defined but unused:** `GET /v1/version`, `get_providers()` (only the vector_io filter variant is used).

---

## High-Priority Improvements (Stable v1 APIs)

### 1. Safety / Content Moderation

**Endpoints:**
- `GET /v1/shields` — list available safety shields
- `POST /v1/safety/run-shield` — run shield on messages (`shield_id`, `messages[]`)
- `POST /v1/moderations` — OpenAI-compatible content moderation (`model`, `input`)

**What to build:**
- Add a toggle in Settings to enable safety shields per chat session
- Run input messages through a shield before sending to the LLM
- Run LLM responses through a shield before displaying
- Show violation info (level: INFO/WARN/ERROR, description) inline in chat
- This aligns with the repo's commit history which references shields work

---

### 2. Responses API (Agentic Workflows)

**Endpoints:**
- `POST /v1/responses` — create a response with tool use support
- `GET /v1/responses` — list responses
- `GET /v1/responses/{id}` — retrieve a response
- `DELETE /v1/responses/{id}` — delete a response

**What to build:**
- Add an "Agent Mode" toggle in chat that uses the Responses API instead of raw chat completions
- Support built-in tools: `web_search`, `file_search`, `code_interpreter`
- Support `function` tool definitions (user-defined tools)
- Support MCP connector tools
- Display tool call steps and results inline in the chat (e.g., show "Searching web..." then the search results)
- Use `previous_response_id` for multi-turn agentic conversations

---

### 3. Tool / Function Calling in Chat

**Endpoint:** `POST /v1/chat/completions` with `tools` and `tool_choice` parameters (already exists, just not used)

**What to build:**
- A tool definition UI where users can define function schemas (name, description, parameters)
- Pass tools to chat completions, handle `tool_calls` in the response delta
- Display tool call requests and let users provide tool results, or auto-execute known tools
- This is simpler than the full Responses API and works with the existing streaming infrastructure

---

### 4. Conversations API (Server-Side Chat History)

**Endpoints:**
- `POST /v1/conversations` — create a conversation
- `GET /v1/conversations/{id}` — retrieve a conversation
- `DELETE /v1/conversations/{id}` — delete a conversation
- `GET /v1/conversations/{id}/items` — list items
- `POST /v1/conversations/{id}/items` — add items

**What to build:**
- Replace client-side `st.session_state.messages` with server-side conversation storage
- Add a conversation list sidebar (past conversations)
- Conversations persist across browser refreshes
- Search across past conversations

---

### 5. Embeddings API

**Endpoint:** `POST /v1/embeddings` — generate embedding vectors (`model`, `input`)

**What to build:**
- "Test Embedding" feature on the Documents page — enter text, see the vector
- Similarity calculator — compare two texts by cosine similarity of their embeddings
- Useful for debugging RAG: check if a query is semantically close to stored chunks

---

### 6. File Management Improvements

**Available but unused endpoints:**
- `GET /v1/files` — list all uploaded files
- `GET /v1/files/{id}` — get file metadata
- `GET /v1/files/{id}/content` — download file content
- `DELETE /v1/files/{id}` — delete a file
- `DELETE /v1/vector_stores/{id}/files/{file_id}` — remove a file from a vector store
- `GET /v1/vector_stores/{id}/files/{file_id}/content` — retrieve file content with optional embeddings

**What to build:**
- A file manager view (list all files, see metadata, delete orphaned files)
- Remove individual files from vector stores (currently only full store deletion)
- File content preview — view the stored chunks and their metadata
- Download original file content

---

### 7. Vector Store Search Improvements

**Available but unused parameters on `POST /v1/vector_stores/{id}/search`:**
- `filters` — metadata-based filtering
- `ranking_options` — control ranking behavior
- `rewrite_query` — automatic query rewriting for better retrieval

**What to build:**
- Expose `rewrite_query` as a toggle in the RAG sidebar (let the LLM rewrite the user's question for better retrieval)
- Add metadata filters for search (e.g., filter by filename, date)
- Add a standalone search UI on the Documents page for testing retrieval quality

---

### 8. Batch File Ingestion

**Endpoints:**
- `POST /v1/vector_stores/{id}/file_batches` — bulk file ingestion
- `GET /v1/vector_stores/{id}/file_batches/{batch_id}` — check batch status

**What to build:**
- When uploading multiple files, use batch API instead of one-by-one uploads
- Show batch progress status
- Significant performance improvement for large case uploads

---

### 9. Prompt Templates

**Endpoints:**
- `GET /v1/prompts` — list prompts
- `POST /v1/prompts` — create a prompt
- `GET /v1/prompts/{id}` — get a prompt (with versioning)
- `PUT /v1/prompts/{id}` — update a prompt

**What to build:**
- Replace the single system prompt text area in Settings with a prompt template manager
- Save/load multiple prompt templates with version history
- Select which prompt template to use per chat session

---

## Medium-Priority (Experimental APIs)

### 10. Evaluation & Scoring (`/v1alpha`, `/v1`)

**Endpoints:**
- `GET /v1/scoring-functions` — list scoring functions
- `POST /v1/scoring/score` — score model outputs
- `GET /v1alpha/eval/benchmarks` — list benchmarks
- `POST /v1alpha/eval/benchmarks/{id}/jobs` — run evaluation

**What to build:**
- An "Evaluate" page where users can score model outputs against scoring functions
- Run benchmarks against the configured model
- Compare model performance across different configurations

---

### 11. Reranking (`/v1alpha`)

**Endpoint:** `POST /v1alpha/inference/rerank` — rerank documents by query relevance

**What to build:**
- Add a reranking step to the RAG pipeline: retrieve top-N chunks, rerank them, use top-K
- This can significantly improve RAG answer quality, especially with larger initial retrieval sets

---

### 12. Admin / Diagnostics (`/v1alpha`)

**Endpoints:**
- `GET /v1alpha/admin/providers` — providers with health status
- `GET /v1alpha/admin/inspect/routes` — all available routes
- `GET /v1alpha/admin/health` — detailed health
- `GET /v1/version` — server version (already defined, unused)

**What to build:**
- A diagnostics/status panel on the Settings page showing:
  - Server version
  - Provider health status
  - Available API routes
  - Which features are available on the connected server

---

## Quick Wins (minimal effort, immediate value)

| Improvement | Effort | Impact |
|-------------|--------|--------|
| Show server version on Settings page (endpoint already coded) | Low | Helps debugging |
| Add `rewrite_query: true` to vector store search | Low | Better RAG results |
| Use batch file upload API for multi-file uploads | Low | Faster uploads |
| Add standalone search box on Documents page | Low | Debug RAG quality |
| Remove individual files from vector stores | Low | Better document management |
| List all uploaded files with delete option | Low | Clean up orphaned files |
| Show provider details on Settings page (method already coded) | Low | Better visibility |
| Add shields toggle to chat (if shields available on server) | Medium | Content safety |
| Add tool calling support to chat completions | Medium | Much richer chat capabilities |
| Use Conversations API for persistent chat history | Medium | Chat survives page refresh |
