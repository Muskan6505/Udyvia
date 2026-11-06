import pytest

from app.services import llm


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch):
    """Tests never call the real Gemini API, even if a key is configured in .env."""
    monkeypatch.setattr(llm, "get_llm", lambda: None)
    monkeypatch.setattr(llm, "_down_until", 0.0)
