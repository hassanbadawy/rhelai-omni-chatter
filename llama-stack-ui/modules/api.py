import json
import logging
import re

import requests

from modules.config import load_config

logger = logging.getLogger(__name__)


class LlamaStackClient:
    @property
    def base_url(self):
        config = load_config()
        return config.get("endpoint", "")

    def get_models(self, model_type=None):
        """Fetch available models from /v1/models.
        Handles both Llama Stack format (identifier/model_type/custom_metadata)
        and OpenAI format (id).
        """
        resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])

        result = []
        for m in models:
            model_id = m.get("identifier") or m.get("id", "")
            cm = m.get("custom_metadata", {})
            m_type = m.get("model_type") or cm.get("model_type", "llm")
            if model_type and m_type != model_type:
                continue
            result.append({
                "id": model_id,
                "model_type": m_type,
                "provider_id": m.get("provider_id") or cm.get("provider_id", ""),
                "metadata": m.get("metadata", cm),
                "raw": m,
            })
        return result

    def get_llm_models(self):
        """Fetch only LLM models (not embedding models)."""
        return self.get_models(model_type="llm")

    def get_model_context_length(self, model_id):
        """Get the max context length for a model.
        Tries model metadata first, then probes with a minimal request."""
        # 1) Check model metadata
        try:
            models = self.get_models()
            for m in models:
                if m["id"] == model_id:
                    metadata = m.get("metadata", {})
                    raw = m.get("raw", {})
                    for key in ["max_seq_len", "context_length", "max_context_length",
                                "max_model_len", "context_window"]:
                        val = metadata.get(key) or raw.get(key)
                        if val:
                            logger.info("Model %s context length: %s (from metadata.%s)", model_id, val, key)
                            return int(val)
                    logger.info("Model %s metadata keys: %s", model_id, list(metadata.keys()))
        except Exception as e:
            logger.warning("Failed to fetch model metadata for %s: %s", model_id, e)

        # 2) Probe: send an intentionally large max_tokens to trigger an error
        #    that reveals the actual context length
        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 999999,
                    "stream": False,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return None
            body = resp.text
            match = re.search(r"maximum context length is (\d+) tokens", body)
            if match:
                ctx = int(match.group(1))
                logger.info("Model %s context length: %d (from probe)", model_id, ctx)
                return ctx
        except Exception as e:
            logger.warning("Context length probe failed for %s: %s", model_id, e)

        return None

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
        logger.info("Chat completions stream to %s/v1/chat/completions", self.base_url)
        logger.debug("Payload: %s", json.dumps(payload, default=str))
        with requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            logger.info("Chat completions stream status: %d", resp.status_code)
            resp.raise_for_status()
            line_count = 0
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                line_count += 1
                if line_count <= 5:
                    logger.info("SSE line %d: %s", line_count, line[:200])
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    logger.info("Stream finished ([DONE]) after %d lines", line_count)
                    break
                try:
                    chunk = json.loads(data)
                    if "error" in chunk:
                        error_msg = chunk["error"].get("message", str(chunk["error"]))
                        logger.error("Server error in stream: %s", error_msg)
                        raise RuntimeError(error_msg)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (KeyError, IndexError) as e:
                    logger.warning("Failed to parse chunk: %s — raw: %s", e, data[:200])
                    continue
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in stream: %s — raw: %s", e, data[:200])
                    continue
            logger.info("Stream ended, total lines: %d", line_count)

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
            cm = m.get("custom_metadata", {})
            m_type = m.get("model_type") or cm.get("model_type", "llm")
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
            cm = m.get("custom_metadata", {})
            m_type = m.get("model_type") or cm.get("model_type", "llm")
            if m_type != "embedding":
                continue
            model_id = m.get("identifier") or m.get("id", "")
            dim = m.get("metadata", {}).get("embedding_dimension") or cm.get("embedding_dimension", "")
            result.append({"id": model_id, "dimension": dim})
        return result

    def get_vector_io_providers_from(self, base_url):
        """Fetch vector_io providers from a specific endpoint URL.
        Returns list of {"provider_id": str, "provider_type": str}.
        """
        resp = requests.get(f"{base_url}/v1/providers", timeout=10)
        resp.raise_for_status()
        providers = resp.json().get("data", resp.json() if isinstance(resp.json(), list) else [])
        return [
            {"provider_id": p.get("provider_id"), "provider_type": p.get("provider_type", "")}
            for p in providers
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
            "provider_id": provider_id,
        }
        if embedding_dimension:
            try:
                payload["embedding_dimension"] = int(embedding_dimension)
            except (ValueError, TypeError):
                pass
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


    # --- Guardrails Orchestrator Gateway ---

    def guardrails_chat(self, gateway_url, route, messages, model, **kwargs):
        """Send chat through the Guardrails Orchestrator Gateway."""
        gw_model = model.split("/")[-1] if "/" in model else model
        payload = {"messages": messages, "model": gw_model, "stream": False, **kwargs}
        resp = requests.post(
            f"{gateway_url.rstrip('/')}/{route}/v1/chat/completions",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    # --- External Guardrails Detectors ---

    def check_external_detector(self, detector_url, text, threshold=0.5):
        """Call an external guardrails detector service.
        POST {detector_url}/api/v1/text/contents
        Returns list of detections (empty = clean).
        """
        try:
            resp = requests.post(
                f"{detector_url.rstrip('/')}/api/v1/text/contents",
                json={
                    "contents": [text],
                    "detector_params": {"threshold": threshold},
                },
                timeout=5,
            )
            resp.raise_for_status()
            result = resp.json()
            if result and isinstance(result, list) and isinstance(result[0], list):
                return result[0]
            return []
        except requests.RequestException:
            return []

    def run_external_detectors(self, text, detectors, direction="input"):
        """Run all enabled external detectors for a given direction.
        Returns list of {"detector_name", "detection_type", "score", "text"}.
        """
        if not text or not text.strip():
            return []
        violations = []
        for det in detectors:
            if not det.get("enabled", True):
                continue
            apply_to = det.get("apply_to", "both")
            if apply_to != "both" and apply_to != direction:
                continue
            detections = self.check_external_detector(
                det["url"], text, det.get("threshold", 0.5)
            )
            for d in detections:
                violations.append({
                    "detector_name": det.get("name", det.get("url", "Unknown")),
                    "detection_type": d.get("detection_type", "unknown"),
                    "score": d.get("score", 0),
                    "text": d.get("text", ""),
                })
        return violations

    def run_regex_filters(self, text, regex_filters, direction="input"):
        """Run regex pattern filters on text.
        Returns list of {"detector_name", "detection_type", "score", "text"}.
        """
        if not text or not text.strip():
            return []
        violations = []
        for rf in regex_filters:
            if not rf.get("enabled", True):
                continue
            apply_to = rf.get("apply_to", "both")
            if apply_to != "both" and apply_to != direction:
                continue
            try:
                matches = re.findall(rf["pattern"], text, re.IGNORECASE)
                if matches:
                    matched_text = ", ".join(str(m) for m in matches[:5])
                    violations.append({
                        "detector_name": rf.get("name", "Regex Filter"),
                        "detection_type": "REGEX_MATCH",
                        "score": 1.0,
                        "text": matched_text,
                    })
            except re.error:
                continue
        return violations

    # --- Safety / Shields API ---

    def get_shields(self):
        """List available safety shields from /v1/shields"""
        try:
            resp = requests.get(f"{self.base_url}/v1/shields", timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except requests.RequestException:
            return []

    def get_shields_from(self, base_url):
        """List available safety shields from a specific endpoint."""
        try:
            resp = requests.get(f"{base_url}/v1/shields", timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except requests.RequestException:
            return []

    def register_shield(self, shield_id, provider_shield_id, provider_id=None, config=None):
        """Register a safety shield on the server."""
        payload = {
            "shield_id": shield_id,
            "provider_shield_id": provider_shield_id,
        }
        if provider_id:
            payload["provider_id"] = provider_id
        if config:
            payload["config"] = config
        resp = requests.post(
            f"{self.base_url}/v1/shields",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_safety_providers(self):
        """Fetch safety providers from /v1/providers"""
        try:
            resp = requests.get(f"{self.base_url}/v1/providers", timeout=10)
            resp.raise_for_status()
            providers = resp.json().get("data", resp.json() if isinstance(resp.json(), list) else [])
            return [
                {"provider_id": p.get("provider_id"), "provider_type": p.get("provider_type", "")}
                for p in providers
                if isinstance(p, dict) and p.get("api") == "safety"
            ]
        except requests.RequestException:
            return []

    def run_shield(self, shield_id, messages):
        """Run a safety shield on messages.
        Returns the violation dict if content is flagged, None if safe.
        """
        payload = {
            "shield_id": shield_id,
            "messages": messages,
        }
        resp = requests.post(
            f"{self.base_url}/v1/safety/run-shield",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("violation")

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
        logger.info("Streaming request to %s/v1/responses", self.base_url)
        logger.debug("Payload: %s", json.dumps(payload, default=str))
        with requests.post(
            f"{self.base_url}/v1/responses",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            logger.info("Stream response status: %d", resp.status_code)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                logger.debug("SSE raw line: %s", line[:200])
                if not line.startswith("data: "):
                    logger.info("Non-data SSE line: %s", line[:200])
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    logger.info("Stream finished ([DONE])")
                    break
                try:
                    event = json.loads(data)
                    etype = event.get("type", "")
                    logger.info("SSE event type: %s", etype)
                    if etype == "response.output_text.delta":
                        delta = event.get("delta", "")
                        if delta:
                            yield {"type": "delta", "text": delta}
                    elif etype == "response.completed":
                        completed = event.get("response", {})
                        yield {"type": "completed", "response": completed}
                    elif etype == "response.failed":
                        error = event.get("response", {}).get("error", {})
                        msg = error.get("message", "Unknown error")
                        logger.error("Server returned response.failed: %s", msg)
                        yield {"type": "error", "message": msg}
                    else:
                        logger.info("Unhandled SSE event: %s", json.dumps(event, default=str)[:300])
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to parse SSE data: %s — raw: %s", e, data[:200])
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
