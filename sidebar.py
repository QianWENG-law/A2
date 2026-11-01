import streamlit as st


def render_credentials_sidebar():
    """Sidebar input for the user's own OpenAI API key."""
    with st.sidebar:
        key = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
    return key or None
