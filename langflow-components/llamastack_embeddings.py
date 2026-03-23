"""LlamaStack Embeddings component for Langflow.

Works with Llama Stack's /v1/embeddings endpoint.
Ensures all inputs are plain strings to avoid validation errors.
"""

from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import IntInput, MessageTextInput, SecretStrInput


class LlamaStackEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "LlamaStack Embeddings"
    description = "Generate embeddings using Llama Stack's /v1/embeddings endpoint. Compatible with Milvus."
    icon = "LlamaStack"
    name = "LlamaStackEmbeddings"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Embedding Model",
            advanced=False,
            info="The embedding model ID registered in Llama Stack.",
            value="sentence-transformers/nomic-ai/nomic-embed-text-v1.5",
        ),
        MessageTextInput(
            name="api_base",
            display_name="LlamaStack API Base",
            advanced=False,
            info="The base URL of the Llama Stack API server.",
            value="http://llama-stack-service:8321/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key (use 'fake' for local servers).",
            advanced=False,
            value="fake",
            required=False,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            advanced=True,
            value=8,
            info="Number of texts to embed per API call.",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        api_key = self.api_key if self.api_key and self.api_key.strip() else "fake"

        return OpenAIEmbeddings(
            model=self.model_name,
            base_url=self.api_base or "http://llama-stack-service:8321/v1",
            api_key=api_key,
            chunk_size=self.chunk_size,
            check_embedding_ctx_length=False,
        )
