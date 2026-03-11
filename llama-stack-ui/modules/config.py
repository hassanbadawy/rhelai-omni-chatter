import json
import os

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
CONVERSATIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "conversations.json")

DEFAULTS = {
    "endpoint": "",
    "model": "",
    "embedding_model": "",
    "vector_io_provider": "",
    "user_id": "",
    "language": "English",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 1024,
}


def load_config():
    """Load config from YAML file, falling back to defaults."""
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            saved = yaml.safe_load(f)
            if saved:
                config.update(saved)
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
