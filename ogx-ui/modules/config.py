import json
import os

import yaml

_DEFAULT_DIR = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.environ.get("LLAMA_STACK_UI_DATA_DIR", _DEFAULT_DIR)
os.makedirs(_DATA_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(_DATA_DIR, "config.yaml")
CONVERSATIONS_PATH = os.path.join(_DATA_DIR, "conversations.json")

DEFAULTS = {
    "endpoint": os.environ.get("LLAMA_STACK_API_ENDPOINT", ""),
    "model": os.environ.get("DEFAULT_MODEL", ""),
    "embedding_model": "",
    "vector_io_provider": "",
    "user_id": "Hasan",
    "language": "English",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 1024,
    "safety_enabled": False,
    # --- NeMo Guardrails (RHOAI 3.5 / OGX) ---
    # OGX does not implement /v1/shields or /v1/safety/run-shield. When
    # guardrails_url is set, safety goes to NeMo /v1/guardrail/checks instead.
    #
    # In-cluster:  https://nemoguardrails.<ns>.svc   (kube-rbac-proxy: needs a
    #              bearer token + service-CA bundle; both auto-detected below)
    # Local dev:   http://localhost:18000            (port-forward of pod :8000,
    #              plain HTTP, no token needed)
    "guardrails_url": os.environ.get("NEMO_GUARDRAILS_URL", ""),
    "guardrails_config_id": os.environ.get("NEMO_GUARDRAILS_CONFIG_ID", "guardrail-config"),
    # Leave blank to auto-detect the pod's service account token / CA bundle.
    "guardrails_token_file": os.environ.get("NEMO_GUARDRAILS_TOKEN_FILE", ""),
    "guardrails_ca_file": os.environ.get("NEMO_GUARDRAILS_CA_FILE", ""),
    "input_shields": [],
    "output_shields": [],
}


def load_config():
    """Load config from YAML file, falling back to defaults.

    Endpoint and model are sourced from env vars (LLAMA_STACK_API_ENDPOINT,
    DEFAULT_MODEL) if config.yaml does not specify them. Container deployments
    rely on this so the chart can inject the backend URL without baking it
    into config.yaml.
    """
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            saved = yaml.safe_load(f)
            if saved:
                config.update(saved)
    if not config.get("endpoint"):
        config["endpoint"] = os.environ.get("LLAMA_STACK_API_ENDPOINT", "")
    if not config.get("model"):
        config["model"] = os.environ.get("DEFAULT_MODEL", "")
    return config


def save_config(config):
    """Save config to YAML file."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def load_conversations():
    """Load the conversations.json file. Returns the full dict."""
    if os.path.exists(CONVERSATIONS_PATH):
        try:
            with open(CONVERSATIONS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_conversations(data):
    """Save the conversations.json file."""
    try:
        with open(CONVERSATIONS_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get_user_chat_names(user_id):
    """Get chat name mappings for a specific user. Returns {chain_key: name}."""
    data = load_conversations()
    return data.get(user_id, {})


def set_user_chat_name(user_id, chain_key, name):
    """Set a chat name for a user."""
    data = load_conversations()
    if user_id not in data:
        data[user_id] = {}
    data[user_id][chain_key] = name
    save_conversations(data)


def remove_user_chat_name(user_id, chain_key):
    """Remove a chat name for a user."""
    data = load_conversations()
    if user_id in data:
        data[user_id].pop(chain_key, None)
        save_conversations(data)


# Standard in-pod locations, used when the guardrails endpoint is an in-cluster
# HTTPS Service fronted by kube-rbac-proxy.
_SA_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
_SA_CA = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"


def guardrails_auth(config):
    """Resolve (token, verify) for the guardrails endpoint.

    Returns (None, None) for a plain-HTTP URL -- local port-forward dev -- and
    (token, ca_path_or_True) for an in-cluster HTTPS Service.
    """
    url = (config.get("guardrails_url") or "").strip()
    if not url.startswith("https://"):
        return None, None

    token_file = config.get("guardrails_token_file") or _SA_TOKEN
    token = None
    if os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()

    ca = config.get("guardrails_ca_file") or (_SA_CA if os.path.exists(_SA_CA) else None)
    return token, (ca or True)


# A "guardrailed" model is a synthetic Settings entry: the same served model,
# but routed through NeMo so rails apply. Selecting it IS how guardrails are
# switched on -- there is no separate toggle.
GUARDRAIL_PREFIX = "guardrailed/"


def is_guardrailed(model_id):
    return bool(model_id) and model_id.startswith(GUARDRAIL_PREFIX)


def strip_guardrail(model_id):
    """Real served-model-name to send upstream."""
    return model_id[len(GUARDRAIL_PREFIX):] if is_guardrailed(model_id) else model_id


def guardrailed_choices(model_ids, config):
    """Original ids plus a guardrailed twin for each, when a guardrails URL is set."""
    if not config.get("guardrails_url"):
        return list(model_ids)
    out = []
    for m in model_ids:
        out.append(m)
        out.append(GUARDRAIL_PREFIX + m)
    return out
