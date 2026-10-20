from types import SimpleNamespace

import pytest

from app.errors import ApiError
from app.pipeline.run import run_pipeline
from app.providers import whisper


class FakeModel:
    def __init__(self, segments):
        self.segments = segments

    def transcribe(self, path, **kwargs):
        return iter(self.segments), SimpleNamespace(language="en")


def seg(*words):
    return SimpleNamespace(words=[SimpleNamespace(word=t, start=s, end=e) for t, s, e in words])


def test_words_extracted_and_trimmed(monkeypatch):
    fake = FakeModel([seg((" Hello", 0.0, 0.4), (" world.", 0.5, 0.9)), seg((" ", 1.0, 1.1))])
    monkeypatch.setattr(whisper, "_get_model", lambda: fake)
    words = whisper.WhisperASR().transcribe("x.wav")
    assert [w.text for w in words] == ["Hello", "world."]
    assert words[1].start == 0.5


def test_no_words_gives_no_speech(monkeypatch, tmp_path):
    import subprocess
    wav = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "3", str(wav)],
                   capture_output=True, check=True)
    monkeypatch.setattr(whisper, "_get_model", lambda: FakeModel([]))
    from app.config import settings
    monkeypatch.setattr(settings, "asr_provider", "whisper")
    monkeypatch.setattr("app.pipeline.run.download_audio", lambda url, d: str(wav))
    with pytest.raises(ApiError) as e:
        run_pipeline({"audio_url": "https://example.com/a.wav"}, str(tmp_path))
    assert e.value.code == "NO_SPEECH_DETECTED"