import streamlit as st

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    OXYLABS_USERNAME = st.secrets["OXYLABS_USERNAME"]
    OXYLABS_PASSWORD = st.secrets["OXYLABS_PASSWORD"]
except KeyError as e:
    raise RuntimeError(f"Missing secret: {e}")