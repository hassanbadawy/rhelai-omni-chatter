from typing import Any

from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DictInput, IntInput, SecretStrInput, SliderInput, StrInput
from lfx.log.logger import logger


class VllmComponent(LCModelComponent):
    display_name = "vLLM"
    description = "Generates text using vLLM models via OpenAI-compatible API."
    icon = "vLLM"
    name = "vLLMModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=2048),
            value=256,
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            info="The name of the vLLM model to use.",
            value="smollm2-135m",
        ),
        StrInput(
            name="api_base",
            display_name="vLLM API Base",
            advanced=False,
            info="The base URL of the vLLM API server.",
            value="http://smollm2-135m-v2-predictor.genai-demo.svc.cluster.local:8080/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the vLLM model (use 'fake' for local servers).",
            advanced=False,
            value="fake",
            required=False,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Controls the reproducibility of the job. Set to -1 to disable.",
            advanced=True,
            value=-1,
            required=False,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="Max retries when generating. Set to -1 to disable.",
            advanced=True,
            value=-1,
            required=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for requests to vLLM completion API. Set to -1 to disable.",
            advanced=True,
            value=-1,
            required=False,
        ),
    ]

    def build_model(self) -> LanguageModel:
        logger.debug(f"Executing request with vLLM model: {self.model_name}")

        # Resolve API key — never pass empty string or None
        api_key = "fake"
        if self.api_key and self.api_key.strip():
            api_key = self.api_key.strip()

        parameters: dict[str, Any] = {
            "api_key": api_key,
            "model": self.model_name,
            "base_url": self.api_base or "http://localhost:8000/v1",
            "temperature": self.temperature if self.temperature is not None else 0.1,
        }

        # Only add max_tokens if set and > 0
        if self.max_tokens and self.max_tokens > 0:
            parameters["max_tokens"] = self.max_tokens

        # Only add model_kwargs if non-empty dict with valid keys
        if self.model_kwargs and isinstance(self.model_kwargs, dict):
            cleaned = {k: v for k, v in self.model_kwargs.items() if k and k.strip()}
            if cleaned:
                parameters["model_kwargs"] = cleaned

        # Only add optional parameters if explicitly set (not -1 or None)
        if self.seed is not None and self.seed != -1:
            parameters["seed"] = self.seed
        if self.timeout is not None and self.timeout != -1:
            parameters["timeout"] = self.timeout
        if self.max_retries is not None and self.max_retries != -1:
            parameters["max_retries"] = self.max_retries

        output = ChatOpenAI(**parameters)
        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return build_config
