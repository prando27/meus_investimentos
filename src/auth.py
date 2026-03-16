"""Simple password gate for the dashboard."""

import hashlib
import hmac
import os

import streamlit as st


def _get_password() -> str:
    """Get the app password from env var or Streamlit secrets."""
    # Try Streamlit secrets first, then env var
    try:
        return st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("APP_PASSWORD", "")


def check_auth():
    """Show a login form and block access until the correct password is entered.

    Does nothing if APP_PASSWORD is not set (local dev without auth).
    """
    password = _get_password()
    if not password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("🔒 Login")
    entered = st.text_input("Senha", type="password", key="login_password")
    if st.button("Entrar"):
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()
