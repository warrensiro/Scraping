import streamlit as st


def get_openai_api_key() -> str:
    """Fetch OpenAI API key from Streamlit secrets at runtime."""
    try:
        return st.secrets["OPENAI_API_KEY"]
    except KeyError as e:
        raise RuntimeError(f"Missing secret: {e}")


def get_oxylabs_credentials() -> tuple[str, str]:
    """Fetch Oxylabs username and password from Streamlit secrets at runtime."""
    try:
        username = st.secrets["OXYLABS_USERNAME"]
        password = st.secrets["OXYLABS_PASSWORD"]
    except KeyError as e:
        raise RuntimeError(f"Missing secret: {e}")
    return username, password