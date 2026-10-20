from pathlib import Path

from app.errors import ApiError
from app.pipeline.audio import probe
from app.providers import get_asr, get_tts
from app.providers.base import Word

SENTENCE_END = (".", "!", "?", "।")


def words_from_text(text: str, voice: str, workdir: str) -> tuple[list[Word], str, float]:
    """Text -> narration audio -> timed words. Returns (words, wav_path, seconds)."""
    if not text or not text.strip():
        raise ApiError("EMPTY_INPUT", "The script is empty.", 400)
    wav = get_tts().speak(text.strip(), voice, str(Path(workdir) / "narration.wav"))
    words = get_asr().transcribe(wav, text_hint=text.strip())
    return words, wav, probe(wav)["duration"]


def text_from_scenes(scenes: list[dict]) -> tuple[str, list[str | None]]:
    """Join a scene list into one script. Returns (text, hint for every word)."""
    parts, word_hints = [], []
    for s in scenes:
        t = (s.get("text") or "").strip()
        if not t:
            continue
        if not t.endswith(SENTENCE_END):
            t += "."          # each given scene ends on a sentence boundary
        parts.append(t)
        word_hints.extend([s.get("visual_hint")] * len(t.split()))
    if not parts:
        raise ApiError("EMPTY_INPUT", "The scene list has no text.", 400)
    return " ".join(parts), word_hints