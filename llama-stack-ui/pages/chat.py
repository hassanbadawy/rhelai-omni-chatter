import streamlit as st

from modules.api import client
from modules.config import (
    load_config,
    get_user_chat_names,
    set_user_chat_name,
    remove_user_chat_name,
)

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


def _extract_text(content):
    """Extract plain text from a response content field (string or list of parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text", ""))
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return str(content)


def _build_chains_from_responses(responses):
    """Group responses into conversation chains using previous_response_id.
    Returns {chain_key: chain} where chain_key is the first response ID."""
    by_id = {r["id"]: r for r in responses}
    children = {}
    for r in responses:
        prev = r.get("previous_response_id")
        if prev:
            children[prev] = r["id"]

    chain_tails = [r["id"] for r in responses if r["id"] not in children]

    chains_by_key = {}
    for tail_id in chain_tails:
        chain = [tail_id]
        current = by_id.get(tail_id)
        while current and current.get("previous_response_id"):
            prev_id = current["previous_response_id"]
            if prev_id in by_id:
                chain.append(prev_id)
                current = by_id[prev_id]
            else:
                break
        chain.reverse()
        chain_key = chain[0]  # first response ID
        chains_by_key[chain_key] = chain

    return chains_by_key, by_id


def _load_chain_messages(chain, by_id):
    """Build the message list for a conversation chain from response data."""
    messages = []
    for resp_id in chain:
        resp = by_id.get(resp_id, {})
        inp = resp.get("input", "")
        user_text = _extract_text(inp)
        if user_text:
            messages.append({"role": "user", "content": user_text})
        for out in resp.get("output", []):
            if out.get("type") == "message" and out.get("role") == "assistant":
                text = _extract_text(out.get("content", ""))
                if text:
                    messages.append({"role": "assistant", "content": text})
    return messages


def chat_page():
    st.title("Chat")

    config = load_config()
    endpoint = config.get("endpoint", "")
    user_id = config.get("user_id", "")

    if not endpoint:
        st.error("No endpoint configured. Please go to **Settings** to configure the endpoint.")
        return

    if not user_id:
        st.error("No User ID configured. Please go to **Settings** to set your User ID.")
        return

    if not client.health():
        st.error("Unable to reach the Llama Stack server. Please go to **Settings** to configure the endpoint.")
        return

    # Read settings from config
    selected_model = config.get("model", "")
    language = config.get("language", "English")
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    temperature = config.get("temperature", 0.7)
    top_p = config.get("top_p", 0.9)
    max_tokens = config.get("max_tokens", 1024)

    if not selected_model:
        try:
            models = client.get_llm_models()
            if models:
                selected_model = models[0]["id"]
        except Exception:
            pass

    if not selected_model:
        st.warning("No model configured. Go to Settings to set endpoint and model.")
        return

    # --- Load responses from server and build chains ---
    try:
        all_responses = client.list_responses(limit=100)
    except Exception as e:
        st.error(f"Failed to load chat history: {e}")
        return

    chains_by_key, by_id = _build_chains_from_responses(all_responses)

    # --- conversations.json is the source of truth for the dropdown ---
    chat_names = get_user_chat_names(user_id)

    # Filter: only show conversations that exist both in conversations.json AND on the server
    valid_keys = [k for k in chat_names if k in chains_by_key]

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

        # Conversation dropdown — always visible, "New Chat" + registered conversations
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
                        # Renaming the "New Chat" — store the pending name for when first message is sent
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
                    chain = chains_by_key.get(selected_key, [])
                    for resp_id in chain:
                        try:
                            client.delete_response(resp_id)
                        except Exception:
                            pass
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
                    vs["id"]: f"{vs.get('name', vs['id'])} ({vs.get('file_counts', {}).get('total', 0)} files)"
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
    messages = []
    last_response_id = None

    if active_key and active_key in chains_by_key:
        chain = chains_by_key[active_key]
        messages = _load_chain_messages(chain, by_id)
        last_response_id = chain[-1]

    # --- Display chat history ---
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- Process prompt ---
    def process_prompt(prompt):
        nonlocal last_response_id

        input_text = prompt
        retrieval_output = ""

        if selected_vector_db:
            try:
                chunks = client.search_vector_store(selected_vector_db, prompt, max_num_results=5)
                retrieval_output = "\n\n".join(chunks)
            except Exception as e:
                st.warning(f"Search failed: {e}")

            if retrieval_output:
                input_text = (
                    f"Please answer the following query using the context below.\n\n"
                    f"CONTEXT:\n{retrieval_output}\n\n"
                    f"QUERY:\n{prompt}"
                )

        with st.chat_message("assistant"):
            if retrieval_output:
                with st.expander("Retrieval Output", expanded=False):
                    st.write(retrieval_output)

            message_placeholder = st.empty()
            full_response = ""
            new_response_id = None

            try:
                for event in client.create_response(
                    model=selected_model,
                    input_text=input_text,
                    previous_response_id=last_response_id,
                    instructions=system_prompt.strip() if system_prompt.strip() else None,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    stream=True,
                ):
                    if event["type"] == "delta":
                        full_response += event["text"]
                        message_placeholder.markdown(full_response + "\u258c")
                    elif event["type"] == "completed":
                        new_response_id = event["response"].get("id")

                message_placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"Error: {e}"
                message_placeholder.error(full_response)

            # Register new conversation in conversations.json on first message
            if new_response_id:
                if not active_key:
                    # This is a new chat — the chain_key is the first response ID
                    chain_key = new_response_id
                    # Use pending name from pre-rename, or default to first 40 chars
                    pending_name = st.session_state.pop("pending_chat_name", None)
                    default_name = pending_name or (prompt[:40] + ("..." if len(prompt) > 40 else ""))
                    set_user_chat_name(user_id, chain_key, default_name)
                    st.session_state.active_chat_key = chain_key

                last_response_id = new_response_id
                st.session_state._last_response_id = new_response_id

    # --- Chat input ---
    if prompt := st.chat_input("Type your message..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.pending_prompt = prompt
        st.rerun()

    if st.session_state.get("pending_prompt"):
        process_prompt(st.session_state.pending_prompt)
        st.session_state.pending_prompt = None


chat_page()
