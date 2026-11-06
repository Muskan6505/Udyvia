import pytest

from app.services import llm, tts


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch):
    """Tests never call the real Gemini API, even if a key is configured in .env."""
    monkeypatch.setattr(llm, "get_llm", lambda: None)
    monkeypatch.setattr(llm, "_down_until", 0.0)
    monkeypatch.setattr(tts, "get_client", lambda: None)
    monkeypatch.setattr(tts, "configured", lambda: False)
    monkeypatch.setattr(tts, "_down_until", 0.0)


@pytest.fixture(autouse=True)
def audit_to_tmp(monkeypatch, tmp_path):
    """Each test gets its own audit log, so tests never write into the repo."""
    from app.privacy import audit
    monkeypatch.setattr(audit, "LOG", tmp_path / "audit.log")
