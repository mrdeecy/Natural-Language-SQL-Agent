from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value

    try:
        import streamlit as st

        secret = st.secrets.get(name)
        if secret is not None:
            return str(secret)
    except Exception:
        pass

    return default


OPENAI_API_KEY = get_setting("OPENAI_API_KEY")
CHAT_MODEL = get_setting("CHAT_MODEL", "gpt-4o-mini")
CONFIDENCE_THRESHOLD = float(get_setting("CONFIDENCE_THRESHOLD", "0.75"))
MAX_RETRIES = int(get_setting("MAX_RETRIES", "3"))
DATABASE_URL = (
    get_setting("SUPABASE_DB_URL")
    or get_setting("DATABASE_URL")
    or "postgresql://sql_agent:password@localhost:5432/pagila"
)

LANGCHAIN_API_KEY = get_setting("LANGCHAIN_API_KEY") or get_setting("LANGSMITH_KEY")
LANGCHAIN_PROJECT = get_setting("LANGCHAIN_PROJECT") or get_setting("LANGSMITH_PROJECT", "nl-sql-agent")
LANGCHAIN_TRACING_V2 = (
    bool(LANGCHAIN_API_KEY)
    and (
        get_setting("LANGCHAIN_TRACING_V2")
        or get_setting("LANGSMITH_TRACING", "true")
    ).lower() == "true"
)
LANGCHAIN_ENDPOINT = get_setting("LANGCHAIN_ENDPOINT") or get_setting("LANGSMITH_ENDPOINT")
