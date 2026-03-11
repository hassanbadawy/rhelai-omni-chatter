import streamlit as st

from modules.api import client
from modules.config import load_config


def documents_page():
    st.title("Documents")

    config = load_config()
    embedding_model = config.get("embedding_model", "")
    embedding_dimension = config.get("embedding_dimension", "")
    vector_io_provider = config.get("vector_io_provider", "")

    if not config.get("endpoint"):
        st.warning("No endpoint configured. Go to Settings first.")
        return

    # --- Create New Case ---
    st.subheader("Create New Case")
    with st.form("create_case", clear_on_submit=True):
        case_name = st.text_input("Case Name", placeholder="e.g. police_case_004")
        uploaded_files = st.file_uploader(
            "Upload files",
            accept_multiple_files=True,
            type=["txt", "pdf", "doc", "docx"],
        )
        submitted = st.form_submit_button("Create Case", type="primary")

        if submitted:
            if not case_name.strip():
                st.error("Please enter a case name.")
            elif not embedding_model:
                st.error("No embedding model configured. Go to Settings.")
            else:
                with st.spinner("Creating case..."):
                    try:
                        vs = client.create_vector_store(
                            name=case_name.strip(),
                            embedding_model=embedding_model,
                            embedding_dimension=embedding_dimension,
                            provider_id=vector_io_provider,
                        )
                        vs_id = vs.get("id", "")
                        st.success(f"Case **{case_name}** created ({vs_id})")

                        if uploaded_files:
                            _upload_files_to_store(vs_id, uploaded_files)
                    except Exception as e:
                        st.error(f"Failed to create case: {e}")

    st.divider()

    # --- Existing Cases ---
    st.subheader("Existing Cases")
    try:
        vector_stores = client.get_vector_stores()
    except Exception as e:
        st.error(f"Failed to fetch cases: {e}")
        return

    if not vector_stores:
        st.info("No cases found.")
        return

    for vs in vector_stores:
        vs_id = vs["id"]
        vs_name = vs.get("name", vs_id)
        file_counts = vs.get("file_counts", {})
        total_files = file_counts.get("total", 0)

        with st.expander(f"{vs_name} ({total_files} files)", expanded=False):
            st.caption(f"ID: `{vs_id}`")
            st.caption(f"Provider: `{vs.get('metadata', {}).get('provider_id', 'N/A')}`")

            # List files in this case
            try:
                files = client.list_vector_store_files(vs_id)
                if files:
                    st.markdown("**Files:**")
                    for f in files:
                        fname = f.get("filename", f.get("id", "unknown"))
                        st.text(f"  {fname}")
            except Exception:
                pass

            st.divider()

            # Upload more files to this case
            upload_key = f"upload_{vs_id}"
            new_files = st.file_uploader(
                "Add files to this case",
                accept_multiple_files=True,
                type=["txt", "pdf", "doc", "docx"],
                key=upload_key,
            )
            if new_files:
                if st.button("Upload", key=f"btn_upload_{vs_id}"):
                    with st.spinner("Uploading..."):
                        _upload_files_to_store(vs_id, new_files)

            st.divider()

            # Delete case
            if st.button("Delete Case", key=f"btn_del_{vs_id}", type="secondary"):
                st.session_state[f"confirm_del_{vs_id}"] = True

            if st.session_state.get(f"confirm_del_{vs_id}"):
                st.warning(f"Are you sure you want to delete **{vs_name}**?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Yes, delete", key=f"btn_confirm_{vs_id}"):
                        try:
                            client.delete_vector_store(vs_id)
                            st.success(f"Deleted **{vs_name}**")
                            del st.session_state[f"confirm_del_{vs_id}"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete: {e}")
                with col2:
                    if st.button("Cancel", key=f"btn_cancel_{vs_id}"):
                        del st.session_state[f"confirm_del_{vs_id}"]
                        st.rerun()


def _upload_files_to_store(vector_store_id, files):
    """Upload multiple files and attach them to a vector store."""
    success = 0
    for f in files:
        try:
            uploaded = client.upload_file(f.name, f.getvalue())
            file_id = uploaded.get("id", "")
            client.attach_file_to_vector_store(vector_store_id, file_id)
            success += 1
        except Exception as e:
            st.error(f"Failed to upload {f.name}: {e}")
    if success:
        st.success(f"Uploaded {success}/{len(files)} file(s)")


documents_page()
