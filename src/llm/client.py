"""
llm/client.py

Thin wrapper around the OpenAI SDK. Safe to import even when no API key is
configured -- is_available() lets calling code check before attempting a
real call, and get_client() never raises on missing keys (returns None
instead), so the rest of the app can always fall back gracefully.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env if present; harmless no-op if it doesn't exist
except ImportError:
    pass

_API_KEY = os.environ.get("OPENAI_API_KEY")
_MODEL = os.environ.get("CARBONWISE_LLM_MODEL", "gpt-4o-mini")  # cheap, fast model is enough for this task


def is_available() -> bool:
    """Whether an API key is configured. Does NOT guarantee the key is valid
    or that the network call will succeed -- callers must still handle
    failures at call time."""
    return bool(_API_KEY)


def get_client():
    """Returns an OpenAI client, or None if no key is configured. Never raises."""
    if not _API_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=_API_KEY)
    except Exception:
        return None


def get_model() -> str:
    return _MODEL
