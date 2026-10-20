import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def mock_providers(monkeypatch, tmp_path):
    for name in ("asr_provider", "tts_provider", "llm_provider", "footage_provider"):
        monkeypatch.setattr(settings, name, "mock")
    monkeypatch.setattr(settings, "image_provider", "mock")
    monkeypatch.setattr(settings, "image_output_dir", str(tmp_path / "images"))