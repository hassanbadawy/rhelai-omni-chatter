import sys
import os

# Add the current directory to Python path for module imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import streamlit as st

st.set_page_config(page_title="LLM Playground", page_icon="🦙", layout="wide")


def main():
    pages = {
        "Chat": ("pages/chat.py", "💬"),
        "Documents": ("pages/documents.py", "📄"),
        "Settings": ("pages/settings.py", "⚙️"),
    }

    nav_items = [
        st.Page(path, title=name, icon=icon, default=(name == "Chat"))
        for name, (path, icon) in pages.items()
    ]

    pg = st.navigation({"Playground": nav_items}, expanded=False)
    pg.run()


if __name__ == "__main__":
    main()
