import streamlit as st

from modules.api import client
from modules.config import load_config, save_config


def settings_page():
    st.title("Settings")

    config = load_config()

    # --- User ID ---
    st.subheader("User")
    user_id = st.text_input(
        "User ID",
        value=config.get("user_id", ""),
        placeholder="e.g. john.doe",
    )

    st.divider()

    # --- Endpoint Configuration ---
    st.subheader("Endpoint")
    new_endpoint = st.text_input(
        "API Endpoint URL",
        value=config.get("endpoint", ""),
        placeholder="https://your-llm-server.com",
    )

    # Test connection button
    endpoint_ok = False
    if new_endpoint:
        url = new_endpoint.rstrip("/")
        if st.button("Test Connection"):
            with st.spinner("Testing..."):
                if client.health(base_url=url):
                    st.success(f"Connected to {url}")
                    st.session_state.endpoint_ok = True
                else:
                    st.error(f"Cannot reach {url}")
                    st.session_state.endpoint_ok = False

    # Check if endpoint was previously tested or is the saved one
    saved_endpoint = config.get("endpoint", "")
    if new_endpoint.rstrip("/") == saved_endpoint and saved_endpoint:
        endpoint_ok = True
    elif st.session_state.get("endpoint_ok", False):
        endpoint_ok = True

    if not new_endpoint:
        st.info("Enter an endpoint URL and test the connection to continue.")
        return

    if not endpoint_ok:
        st.warning("Test the connection before configuring settings.")
        return

    st.divider()

    # --- Default Model (dropdown from endpoint) ---
    st.subheader("Default Model")
    url = new_endpoint.rstrip("/")
    model_ids = []
    try:
        model_ids = client.get_llm_models_from(url)
    except Exception as e:
        st.error(f"Failed to fetch models: {e}")

    saved_model = config.get("model", "")
    if model_ids:
        default_index = model_ids.index(saved_model) if saved_model in model_ids else 0
        selected_model = st.selectbox("Model", model_ids, index=default_index)
    else:
        st.warning("No LLM models found at this endpoint.")
        selected_model = ""

    st.divider()

    # --- Embedding Model ---
    st.subheader("Embedding Model")
    embedding_models = []
    try:
        embedding_models = client.get_embedding_models_from(url)
    except Exception as e:
        st.error(f"Failed to fetch embedding models: {e}")

    saved_embedding = config.get("embedding_model", "")
    if embedding_models:
        emb_ids = [m["id"] for m in embedding_models]
        emb_labels = [f"{m['id']} (dim: {m['dimension']})" for m in embedding_models]
        emb_index = emb_ids.index(saved_embedding) if saved_embedding in emb_ids else 0
        selected_embedding = st.selectbox(
            "Embedding Model",
            options=emb_ids,
            format_func=lambda x: emb_labels[emb_ids.index(x)],
            index=emb_index,
        )
        embedding_dimension = embedding_models[emb_ids.index(selected_embedding)]["dimension"]
    else:
        st.warning("No embedding models found at this endpoint.")
        selected_embedding = saved_embedding
        embedding_dimension = ""

    # --- Vector IO Provider ---
    vector_io_providers = []
    try:
        vector_io_providers = client.get_vector_io_providers_from(url)
    except Exception:
        pass

    saved_vio = config.get("vector_io_provider", "")
    if vector_io_providers:
        vio_ids = [p["provider_id"] for p in vector_io_providers]
        vio_labels = [f"{p['provider_id']} ({p['provider_type']})" for p in vector_io_providers]
        vio_index = vio_ids.index(saved_vio) if saved_vio in vio_ids else 0
        selected_vio = st.selectbox(
            "Vector IO Provider",
            options=vio_ids,
            format_func=lambda x: vio_labels[vio_ids.index(x)],
            index=vio_index,
        )
    else:
        selected_vio = saved_vio

    st.divider()

    # --- Safety / Guardrails ---
    st.subheader("Safety Guardrails")
    safety_enabled = st.toggle(
        "Enable Safety Guardrails",
        value=config.get("safety_enabled", False),
    )

    input_shields = []
    output_shields = []

    if safety_enabled:
        st.caption("Shields are managed server-side by Llama Stack. "
                   "Select which shields to run on input and output messages.")

        # Fetch shields from Llama Stack
        shields = []
        try:
            shields = client.get_shields_from(url)
        except Exception:
            pass

        if shields:
            shield_ids = [s.get("identifier") or s.get("shield_id") or s.get("id", "") for s in shields]
            shield_labels = {}
            for s in shields:
                sid = s.get("identifier") or s.get("shield_id") or s.get("id", "")
                provider = s.get("provider_id", "")
                shield_labels[sid] = f"{sid} ({provider})" if provider else sid

            saved_input = config.get("input_shields", [])
            saved_output = config.get("output_shields", [])

            input_shields = st.multiselect(
                "Input Shields (check user messages before sending to LLM)",
                options=shield_ids,
                default=[s for s in saved_input if s in shield_ids],
                format_func=lambda x: shield_labels.get(x, x),
            )
            output_shields = st.multiselect(
                "Output Shields (check LLM responses before displaying)",
                options=shield_ids,
                default=[s for s in saved_output if s in shield_ids],
                format_func=lambda x: shield_labels.get(x, x),
            )
        else:
            st.info("No shields available on this endpoint. "
                    "Deploy Llama Stack with guardrails enabled to use shields.")

    st.divider()

    # --- Sampling Defaults ---
    st.subheader("Sampling Parameters")
    temperature = st.slider("Temperature", 0.0, 2.0, config.get("temperature", 0.7), 0.1)
    top_p = st.slider("Top P", 0.0, 1.0, config.get("top_p", 0.9), 0.05)
    max_tokens = st.number_input(
        "Max Tokens", 1, 8192, config.get("max_tokens", 1024), step=64
    )

    st.divider()

    # --- Default Language ---
    st.subheader("Default Language")
    languages = ["English", "Arabic", "French", "Spanish", "German", "Chinese", "Japanese", "Korean", "Portuguese", "Russian", "Turkish", "Hindi"]
    saved_lang = config.get("language", "English")
    lang_index = languages.index(saved_lang) if saved_lang in languages else 0
    language = st.selectbox("Language", languages, index=lang_index)

    st.divider()

    # --- System Prompt ---
    st.subheader("System Prompt")
    system_prompt = st.text_area(
        "System Prompt",
        value=config.get("system_prompt", "You are a helpful assistant."),
        height=100,
    )

    st.divider()

    # --- Save ---
    if st.button("Save Settings", type="primary", use_container_width=True):
        new_config = {
            "endpoint": url,
            "user_id": user_id,
            "model": selected_model,
            "embedding_model": selected_embedding,
            "embedding_dimension": embedding_dimension,
            "vector_io_provider": selected_vio,
            "safety_enabled": safety_enabled,
            "input_shields": input_shields,
            "output_shields": output_shields,
            "language": language,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        save_config(new_config)
        st.success("Settings saved to config.yaml")
        st.rerun()


settings_page()
