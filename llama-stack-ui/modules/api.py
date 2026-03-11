import json

import requests

from modules.config import load_config


class LlamaStackClient:
    @property
    def base_url(self):
        config = load_config()
        return config.get("endpoint", "")

    def get_models(self, model_type=None):
        """Fetch available models from /v1/models.
        Handles both Llama Stack format (identifier/model_type)
        and OpenAI format (id).
        """
        resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])

        # Normalize to a common format
        result = []
        for m in models:
            model_id = m.get("identifier") or m.get("id", "")
            m_type = m.get("model_type", "llm")
            if model_type and m_type != model_type:
                continue
            result.append({
                "id": model_id,
                "model_type": m_type,
                "provider_id": m.get("provider_id", ""),
                "metadata": m.get("metadata", {}),
                "raw": m,
            })
        return result

    def get_llm_models(self):
        """Fetch only LLM models (not embedding models)."""
        return self.get_models(model_type="llm")

    def chat_completions(self, messages, model, **kwargs):
        """Non-streaming chat completion"""
        payload = {"messages": messages, "model": model, "stream": False, **kwargs}
        resp = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_completions_stream(self, messages, model, **kwargs):
        """Streaming chat completion - yields content chunks"""
        payload = {"messages": messages, "model": model, "stream": True, **kwargs}
        with requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    def health(self, base_url=None):
        """Check server health - tries /v1/health then /health"""
        url = base_url or self.base_url
        for path in ["/v1/health", "/health"]:
            try:
                resp = requests.get(f"{url}{path}", timeout=5)
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                continue
        return False

    def get_llm_models_from(self, base_url):
        """Fetch LLM models from a specific endpoint URL."""
        resp = requests.get(f"{base_url}/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        result = []
        for m in models:
            model_id = m.get("identifier") or m.get("id", "")
            m_type = m.get("model_type", "llm")
            if m_type != "llm":
                continue
            result.append(model_id)
        return result

    def version(self):
        """Get server version info - tries /v1/version then /version"""
        for path in ["/v1/version", "/version"]:
            try:
                resp = requests.get(f"{self.base_url}{path}", timeout=5)
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                continue
        return None

    def get_providers(self):
        """Fetch providers from /v1/providers"""
        try:
            resp = requests.get(f"{self.base_url}/v1/providers", timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except requests.RequestException:
            return []

    def get_vector_stores(self):
        """List vector stores"""
        try:
            resp = requests.get(f"{self.base_url}/v1/vector_stores", timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except requests.RequestException:
            return []

    def get_embedding_models_from(self, base_url):
        """Fetch embedding models from a specific endpoint URL."""
        resp = requests.get(f"{base_url}/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        result = []
        for m in models:
            if m.get("model_type") != "embedding":
                continue
            model_id = m.get("identifier") or m.get("id", "")
            dim = m.get("metadata", {}).get("embedding_dimension", "")
            result.append({"id": model_id, "dimension": dim})
        return result

    def get_vector_io_providers_from(self, base_url):
        """Fetch vector_io providers from a specific endpoint URL."""
        resp = requests.get(f"{base_url}/v1/providers", timeout=10)
        resp.raise_for_status()
        providers = resp.json().get("data", resp.json() if isinstance(resp.json(), list) else [])
        return [
            p.get("provider_id") for p in providers
            if isinstance(p, dict) and p.get("api") == "vector_io"
        ]

    def delete_vector_store(self, vector_store_id):
        """Delete a vector store"""
        resp = requests.delete(
            f"{self.base_url}/v1/vector_stores/{vector_store_id}",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def create_vector_store(self, name, embedding_model, embedding_dimension, provider_id):
        """Create a new vector store"""
        payload = {
            "name": name,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "provider_id": provider_id,
        }
        resp = requests.post(
            f"{self.base_url}/v1/vector_stores",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def upload_file(self, file_name, file_content):
        """Upload a file via multipart form"""
        resp = requests.post(
            f"{self.base_url}/v1/files",
            files={"file": (file_name, file_content)},
            data={"purpose": "assistants"},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def attach_file_to_vector_store(self, vector_store_id, file_id):
        """Attach an uploaded file to a vector store with chunking"""
        payload = {
            "file_id": file_id,
            "chunking_strategy": {
                "type": "static",
                "static": {
                    "max_chunk_size_tokens": 512,
                    "chunk_overlap_tokens": 50,
                },
            },
        }
        resp = requests.post(
            f"{self.base_url}/v1/vector_stores/{vector_store_id}/files",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def list_vector_store_files(self, vector_store_id):
        """List files in a vector store"""
        resp = requests.get(
            f"{self.base_url}/v1/vector_stores/{vector_store_id}/files",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    def search_vector_store(self, vector_store_id, query, max_num_results=5):
        """Search a vector store and return matching text chunks"""
        resp = requests.post(
            f"{self.base_url}/v1/vector_stores/{vector_store_id}/search",
            json={"query": query, "max_num_results": max_num_results},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("data", [])
        chunks = []
        for r in results:
            for c in r.get("content", []):
                text = c.get("text", "").strip()
                if text:
                    chunks.append(text)
        return chunks


    # --- Responses API (server-side chat history) ---

    def list_responses(self, limit=50):
        """List stored responses from the server."""
        resp = requests.get(
            f"{self.base_url}/v1/responses",
            params={"limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("data", [])

    def get_response(self, response_id):
        """Retrieve a single response by ID."""
        resp = requests.get(
            f"{self.base_url}/v1/responses/{response_id}",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_response_input_items(self, response_id):
        """Get the full conversation history for a response (includes chained turns)."""
        resp = requests.get(
            f"{self.base_url}/v1/responses/{response_id}/input_items",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("data", [])

    def create_response(self, model, input_text, previous_response_id=None,
                        instructions=None, temperature=None, top_p=None,
                        max_tokens=None, stream=False):
        """Create a response, optionally chaining to a previous response."""
        payload = {
            "model": model,
            "input": input_text,
            "store": True,
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        if instructions:
            payload["instructions"] = instructions
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if stream:
            payload["stream"] = True

        if stream:
            return self._create_response_stream(payload)

        resp = requests.post(
            f"{self.base_url}/v1/responses",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def _create_response_stream(self, payload):
        """Stream a response, yielding content text chunks."""
        with requests.post(
            f"{self.base_url}/v1/responses",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    etype = event.get("type", "")
                    if etype == "response.output_text.delta":
                        delta = event.get("delta", "")
                        if delta:
                            yield {"type": "delta", "text": delta}
                    elif etype == "response.completed":
                        completed = event.get("response", {})
                        yield {"type": "completed", "response": completed}
                except (json.JSONDecodeError, KeyError):
                    continue

    def delete_response(self, response_id):
        """Delete a stored response."""
        resp = requests.delete(
            f"{self.base_url}/v1/responses/{response_id}",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()



client = LlamaStackClient()
