"""
API Credentials sidebar module.

The user enters their OWN OpenAI API key in the sidebar, so the app never
uses the developer's key (same approach as the course module at
https://github.com/stoneman-mls/openai_credentials).
"""

import os

import streamlit as st


def render_credentials_sidebar() -> str | None:
    """Show the API key input in the sidebar and return the key (or None)."""
    with st.sidebar:
        st.header("🔑 API Credentials")
        st.caption(
            "Enter your own OpenAI API key. It is kept only in this browser "
            "session and is never stored."
        )
        key = st.text_input(
            "OpenAI API key",
            type="password",
            value=st.session_state.get("openai_api_key", ""),
            placeholder="sk-...",
        )
        if key:
            st.session_state["openai_api_key"] = key

        # Local development only: fall back to a .env / environment variable.
        if not key and os.getenv("OPENAI_API_KEY"):
            key = os.getenv("OPENAI_API_KEY")
            st.info("Using OPENAI_API_KEY from the local environment.")

        if key:
            st.success("API key set.")
        else:
            st.warning("Please enter an API key to run the analysis.")
    return key or None
