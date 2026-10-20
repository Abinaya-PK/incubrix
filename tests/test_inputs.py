import subprocess

import pytest

from app.config import settings
from app.errors import ApiError
from app.pipeline.audio import prepare_audio
from app.pipeline.inputs import text_from_scenes, words_from_text


def make_audio(path, source):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", source, "-t", "3", str(path)],
                   capture_output=True, check=True)


def code_of(fn, *args):
    with pytest.raises(ApiError) as e:
        fn(*args)
    return e.value.code


def test_rejects_wrong_extension(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    assert code_of(prepare_audio, str(f), str(tmp_path)) == "UNSUPPORTED_MEDIA_TYPE"


def test_rejects_fake_mp3(tmp_path):
    f = tmp_path / "fake.mp3"
    f.write_text("this is not audio")
    assert code_of(prepare_audio, str(f), str(tmp_path)) == "UNSUPPORTED_MEDIA_TYPE"


def test_silent_audio(tmp_path):
    f = tmp_path / "silent.wav"
    make_audio(f, "anullsrc=r=16000:cl=mono")
    assert code_of(prepare_audio, str(f), str(tmp_path)) == "NO_SPEECH_DETECTED"


def test_good_audio_converted(tmp_path):
    f = tmp_path / "tone.wav"
    make_audio(f, "sine=frequency=440:sample_rate=44100")
    wav, seconds = prepare_audio(str(f), str(tmp_path))
    assert wav.endswith("narration.wav")
    assert 2.8 < seconds < 3.2


def test_too_long(tmp_path, monkeypatch):
    f = tmp_path / "tone.wav"
    make_audio(f, "sine=frequency=440")
    monkeypatch.setattr(settings, "max_audio_minutes", 0)
    assert code_of(prepare_audio, str(f), str(tmp_path)) == "AUDIO_TOO_LONG"


def test_text_input(tmp_path):
    words, wav, seconds = words_from_text("Saving money is easy.", "en-IN-female", str(tmp_path))
    assert len(words) == 4
    assert seconds >= words[-1].end - 0.1


def test_empty_text(tmp_path):
    assert code_of(words_from_text, "   ", "en-IN-female", str(tmp_path)) == "EMPTY_INPUT"


def test_scene_list_keeps_hints():
    text, hints = text_from_scenes([
        {"text": "Save money", "visual_hint": "coins in a jar"},
        {"text": "Plan ahead.", "visual_hint": None},
    ])
    assert text == "Save money. Plan ahead."
    assert len(hints) == len(text.split())
    assert hints[0] == "coins in a jar" and hints[-1] is None