import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def mock_providers(monkeypatch):
    for name in ("asr_provider", "tts_provider", "llm_provider", "footage_provider"):
        monkeypatch.setattr(settings, name, "mock")