import logging

import streamlit as st

from modules.api import client
from modules.config import (
    load_config,
    get_user_chat_names,
    set_user_chat_name,
    remove_user_chat_name,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

SUMMARY_PROMPT = """Analyze the following documents and extract a structured summary.
Respond ONLY in {language}. Use this exact format (no extra text):

**Title:** <case title>

---

**People:** <names of people involved>

---

**Place:** <locations mentioned>

---

**Summary:** <2-3 sentence summary>

---

**Timeline:**
- <event 1>
- <event 2>
- <event 3>

DOCUMENTS:
{context}"""


def _get_conversations():
    """Get the conversations dict from session state."""
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}
    return st.session_state.conversations


def _get_active_messages():
    """Get the message list for the active conversation."""
    convs = _get_conversations()
    active = st.session_state.get("active_chat_key")
    if active and active in convs:
        return convs[active]
    return []


def chat_page():
    st.title("Chat")

    config = load_config()
    endpoint = config.get("endpoint", "")
    user_id = config.get("user_id", "")
    logger.info("Config loaded — endpoint=%s, user_id=%s, model=%s", endpoint, user_id, config.get("model", ""))

    if not endpoint:
        st.error("No endpoint configured. Please go to **Settings** to configure the endpoint.")
        return

    if not user_id:
        st.error("No User ID configured. Please go to **Settings** to set your User ID.")
        return

    if not client.health():
        logger.warning("Health check failed for endpoint %s", endpoint)
        st.error("Unable to reach the Llama Stack server. Please go to **Settings** to configure the endpoint.")
        return

    # Read settings from config
    selected_model = config.get("model", "")
    language = config.get("language", "English")
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    temperature = config.get("temperature", 0.7)
    top_p = config.get("top_p", 0.9)
    max_tokens = config.get("max_tokens", 1024)
    logger.info("Settings — model=%s, language=%s, temperature=%s, top_p=%s, max_tokens=%s",
                selected_model, language, temperature, top_p, max_tokens)

    if not selected_model:
        try:
            models = client.get_llm_models()
            logger.info("No model configured, fetched %d models from server", len(models))
            if models:
                selected_model = models[0]["id"]
                logger.info("Auto-selected model: %s", selected_model)
        except Exception as e:
            logger.error("Failed to fetch models for auto-select: %s", e)

    if not selected_model:
        st.warning("No model configured. Go to Settings to set endpoint and model.")
        return

    # Query server for model context length (cached in session state)
    ctx_cache_key = f"_ctx_len_{selected_model}"
    if ctx_cache_key not in st.session_state:
        st.session_state[ctx_cache_key] = client.get_model_context_length(selected_model)
    context_length = st.session_state[ctx_cache_key]
    if context_length:
        logger.info("Model context length: %d", context_length)

    convs = _get_conversations()
    chat_names = get_user_chat_names(user_id)

    # Valid conversations: exist in both session state and conversations.json
    valid_keys = [k for k in chat_names if k in convs]

    # --- Sidebar ---
    with st.sidebar:
        st.caption(f"Model: **{selected_model}**")

        st.divider()

        st.subheader("Conversations")

        if st.button("New Chat", use_container_width=True, type="primary"):
            st.session_state.active_chat_key = None
            st.session_state.pop("pending_prompt", None)
            st.session_state.pop("show_rename", None)
            st.session_state.pop("confirm_delete_conv", None)
            st.rerun()

        # Conversation dropdown
        all_options = [None] + valid_keys
        all_labels = {None: "New Chat"}
        for k in valid_keys:
            all_labels[k] = chat_names[k]

        active_key = st.session_state.get("active_chat_key")
        if active_key not in all_options:
            active_key = None

        selected_key = st.selectbox(
            "Chat History",
            options=all_options,
            format_func=lambda x: all_labels.get(x, "New Chat"),
            index=all_options.index(active_key),
        )

        if selected_key != st.session_state.get("active_chat_key"):
            st.session_state.active_chat_key = selected_key
            st.session_state.pop("pending_prompt", None)
            st.session_state.pop("show_rename", None)
            st.session_state.pop("confirm_delete_conv", None)
            st.rerun()

        # Rename & Delete buttons
        can_delete = selected_key is not None and len(valid_keys) > 1
        col_rename, col_delete = st.columns(2)
        with col_rename:
            if st.button("Rename", use_container_width=True):
                st.session_state.show_rename = True
                st.session_state.pop("confirm_delete_conv", None)
        with col_delete:
            if st.button("Delete", use_container_width=True, disabled=not can_delete):
                if can_delete:
                    st.session_state.confirm_delete_conv = True
                    st.session_state.pop("show_rename", None)

        # Rename form
        if st.session_state.get("show_rename"):
            if selected_key is not None:
                current_label = chat_names.get(selected_key, selected_key)
            else:
                current_label = "New Chat"
            new_name = st.text_input("New name", value=current_label, key="rename_input")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                if st.button("Save", key="rename_save", use_container_width=True):
                    if new_name.strip() and selected_key is not None:
                        set_user_chat_name(user_id, selected_key, new_name.strip())
                        st.session_state.pop("show_rename", None)
                        st.rerun()
                    elif new_name.strip() and selected_key is None:
                        st.session_state.pending_chat_name = new_name.strip()
                        st.session_state.pop("show_rename", None)
                        st.rerun()
            with r_col2:
                if st.button("Cancel", key="rename_cancel", use_container_width=True):
                    st.session_state.pop("show_rename", None)
                    st.rerun()

        # Delete confirmation
        if st.session_state.get("confirm_delete_conv") and can_delete:
            st.warning("Delete this conversation?")
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                if st.button("Yes, delete", key="conv_del_yes"):
                    convs.pop(selected_key, None)
                    remove_user_chat_name(user_id, selected_key)
                    st.session_state.confirm_delete_conv = False
                    st.session_state.active_chat_key = None
                    st.rerun()
            with d_col2:
                if st.button("Cancel", key="conv_del_no"):
                    st.session_state.confirm_delete_conv = False
                    st.rerun()

        st.divider()

        # --- RAG Section ---
        st.subheader("RAG")
        selected_vector_db = None
        try:
            vector_stores = client.get_vector_stores()
            if vector_stores:
                vs_options = {
                    vs["id"]: f"{vs.get('name', vs['id'])} ({vs.get('file_counts', {}).get('completed', 0)}/{vs.get('file_counts', {}).get('total', 0)} files ready)"
                    for vs in vector_stores
                }
                vs_ids = list(vs_options.keys())
                selected_vector_db = st.selectbox(
                    "Document Collection",
                    options=[None] + vs_ids,
                    format_func=lambda x: "-- General Chat --" if x is None else vs_options[x],
                )
        except Exception as e:
            st.error(f"Failed to fetch vector stores: {e}")

        if selected_vector_db:
            cache_key = f"case_summary_{selected_vector_db}_{language}"

            if cache_key not in st.session_state:
                with st.spinner("Loading case summary..."):
                    try:
                        chunks = client.search_vector_store(
                            selected_vector_db, "summary of the case", max_num_results=10
                        )
                        if chunks:
                            context = "\n\n".join(chunks)
                            result = client.chat_completions(
                                messages=[{"role": "user", "content": SUMMARY_PROMPT.format(context=context, language=language)}],
                                model=selected_model,
                                max_tokens=512,
                            )
                            summary = result["choices"][0]["message"]["content"]
                            st.session_state[cache_key] = summary
                        else:
                            st.session_state[cache_key] = None
                    except Exception:
                        st.session_state[cache_key] = None

            summary = st.session_state.get(cache_key)
            if summary:
                st.markdown(summary)

    # --- Determine active conversation state ---
    active_key = st.session_state.get("active_chat_key")
    messages = _get_active_messages()

    if active_key:
        logger.info("Active conversation: key=%s, messages=%d", active_key, len(messages))
    else:
        logger.info("No active conversation (new chat)")

    # --- Display chat history ---
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- Process prompt ---
    def process_prompt(prompt):
        logger.info("Processing prompt: %s", prompt[:100])

        input_text = prompt
        retrieval_output = ""

        if selected_vector_db:
            logger.info("RAG enabled — searching vector store %s", selected_vector_db)
            try:
                chunks = client.search_vector_store(selected_vector_db, prompt, max_num_results=5)
                retrieval_output = "\n\n".join(chunks)
                logger.info("RAG retrieved %d chunks (%d chars)", len(chunks), len(retrieval_output))
            except Exception as e:
                logger.error("RAG search failed: %s", e)
                st.warning(f"Search failed: {e}")

            if retrieval_output:
                # Truncate RAG context to fit within model context budget
                # Reserve tokens for: system prompt, conversation history, user query, and output
                if context_length:
                    overhead = len(prompt) + len(system_prompt) + 200  # query + system + framing
                    history_chars = sum(len(m["content"]) for m in messages)
                    # ~3 chars per token (conservative) — leave room for output
                    max_context_chars = (context_length * 3) // 2 - overhead - history_chars
                    if max_context_chars < 100:
                        max_context_chars = 100
                    if len(retrieval_output) > max_context_chars:
                        logger.info("Truncating RAG context from %d to %d chars (model context=%d)",
                                    len(retrieval_output), max_context_chars, context_length)
                        retrieval_output = retrieval_output[:max_context_chars]

                input_text = (
                    f"Please answer the following query using the context below.\n\n"
                    f"CONTEXT:\n{retrieval_output}\n\n"
                    f"QUERY:\n{prompt}"
                )

        # --- Input shields check (server-side via Llama Stack) ---
        input_shields = config.get("input_shields", [])
        if config.get("safety_enabled") and input_shields:
            input_blocked = False
            for shield_id in input_shields:
                try:
                    violation = client.run_shield(
                        shield_id,
                        [{"role": "user", "content": input_text}],
                    )
                    if violation:
                        level = violation.get("violation_level", "error")
                        meta = violation.get("metadata", {})
                        if meta.get("status") == "violation":
                            st.error(
                                f"**{shield_id}** blocked input: "
                                f"{violation.get('user_message', 'Content violation detected')}"
                            )
                            input_blocked = True
                except Exception as e:
                    st.warning(f"Shield '{shield_id}' check failed: {e}")

            if input_blocked:
                with st.chat_message("assistant"):
                    st.error("Message blocked by safety guardrails. Please rephrase your message.")
                return

        with st.chat_message("assistant"):
            if retrieval_output:
                with st.expander("Retrieval Output", expanded=False):
                    st.write(retrieval_output)

            message_placeholder = st.empty()
            full_response = ""

            # Build the API message list: system prompt + conversation history + new user message
            api_messages = []
            if system_prompt.strip():
                api_messages.append({"role": "system", "content": system_prompt.strip()})
            api_messages.extend(messages)
            api_messages.append({"role": "user", "content": input_text})

            # Cap max_tokens to fit within model context length
            effective_max_tokens = max_tokens
            if context_length:
                effective_max_tokens = min(max_tokens, context_length // 2)
                # Estimate input tokens (~3 chars/token, conservative) and trim oldest messages to fit
                max_input_tokens = context_length - effective_max_tokens
                while len(api_messages) > 2:  # keep at least system + current user message
                    total_chars = sum(len(m["content"]) for m in api_messages)
                    estimated_tokens = (total_chars // 3) + (len(api_messages) * 4)
                    if estimated_tokens <= max_input_tokens:
                        break
                    # Remove the oldest non-system message
                    start = 1 if api_messages[0]["role"] == "system" else 0
                    removed = api_messages.pop(start)
                    logger.info("Trimmed message (role=%s, len=%d) to fit context", removed["role"], len(removed["content"]))
                logger.info("max_tokens=%d, est_input=~%d tokens, messages=%d (model context=%d)",
                            effective_max_tokens,
                            (sum(len(m["content"]) for m in api_messages) // 3) + (len(api_messages) * 4),
                            len(api_messages), context_length)

            logger.info("Sending chat completion — model=%s, messages=%d, max_tokens=%d",
                        selected_model, len(api_messages), effective_max_tokens)
            try:
                for chunk in client.chat_completions_stream(
                    messages=api_messages,
                    model=selected_model,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=effective_max_tokens,
                ):
                    full_response += chunk
                    message_placeholder.markdown(full_response + "\u258c")
            except Exception as e:
                logger.error("chat_completions_stream failed: %s", e, exc_info=True)
                message_placeholder.error(f"Error: {e}")
                return

            message_placeholder.markdown(full_response)
            logger.info("Response complete — length=%d", len(full_response))

            # --- Output shields check ---
            output_shields = config.get("output_shields", [])
            if config.get("safety_enabled") and output_shields and full_response:
                for shield_id in output_shields:
                    try:
                        violation = client.run_shield(
                            shield_id,
                            [{"role": "user", "content": full_response}],
                        )
                        if violation:
                            meta = violation.get("metadata", {})
                            if meta.get("status") == "violation":
                                message_placeholder.markdown(
                                    "*Response blocked by safety guardrails.*"
                                )
                                st.error(
                                    f"**{shield_id}** blocked response: "
                                    f"{violation.get('user_message', 'Content violation detected')}"
                                )
                    except Exception as e:
                        st.warning(f"Output shield '{shield_id}' check failed: {e}")

            # Store messages in session state
            active = st.session_state.get("active_chat_key")
            if not active:
                # New conversation — generate an ID and register it
                import uuid
                conv_id = str(uuid.uuid4())
                convs[conv_id] = []
                pending_name = st.session_state.pop("pending_chat_name", None)
                default_name = pending_name or (prompt[:40] + ("..." if len(prompt) > 40 else ""))
                set_user_chat_name(user_id, conv_id, default_name)
                st.session_state.active_chat_key = conv_id
                active = conv_id
                logger.info("New conversation created — id=%s, name=%s", conv_id, default_name)

            convs[active].append({"role": "user", "content": prompt})
            convs[active].append({"role": "assistant", "content": full_response})

    # --- Chat input ---
    if prompt := st.chat_input("Type your message..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.pending_prompt = prompt
        st.rerun()

    if st.session_state.get("pending_prompt"):
        with st.chat_message("user"):
            st.markdown(st.session_state.pending_prompt)
        process_prompt(st.session_state.pending_prompt)
        st.session_state.pending_prompt = None


chat_page()
