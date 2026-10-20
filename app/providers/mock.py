import glob
import os
import wave

from app.config import settings
from app.providers.base import (ASRProvider, Candidate, FootageProvider,
                                GenerativeProvider, Judge, LLMProvider,
                                TTSProvider, Word)

MOCK_TEXT = "Saving money is easy when you plan ahead and track every expense."
WORD_SECONDS = 0.4


def _words(text: str) -> list[Word]:
    out, t = [], 0.0
    for w in text.split():
        out.append(Word(w, round(t, 3), round(t + WORD_SECONDS, 3)))
        t += WORD_SECONDS
    return out


class MockASR(ASRProvider):
    def transcribe(self, audio_path: str, text_hint: str | None = None) -> list[Word]:
        return _words(text_hint or MOCK_TEXT)

class MockTTS(TTSProvider):
    def speak(self, text: str, voice: str, out_path: str) -> str:
        seconds = max(1.0, len(text.split()) * WORD_SECONDS)
        rate = 16000
        with wave.open(out_path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(rate)
            f.writeframes(b"\x00\x00" * int(rate * seconds))
        return out_path


class MockLLM(LLMProvider):
    def analyze_scene(self, text, visual_hint=None, avoid=None) -> dict:
        base = visual_hint or text
        return {
            "queries": [base, f"{base} close up"],
            "sense": None,
            "is_abstract": False,
            "warnings": [],
            "avoid": avoid or [],
        }


class MockFootage(FootageProvider):
    name = "mock"

    def search(self, query: str, min_duration: float = 0.0) -> list[Candidate]:
        out = []
        for path in sorted(glob.glob(os.path.join(settings.fixtures_dir, "clip_*.mp4"))):
            out.append(Candidate(
                source="mock", id=os.path.basename(path), url=path,
                licence="CC0-1.0", attribution="IncuBrix test fixture",
                commercial_ok=True, watermark=False,
                duration=6.0, width=640, height=360))
        return [c for c in out if c.duration >= min_duration]


class MockGenerative(GenerativeProvider):
    def generate(self, prompt: str, duration: float) -> Candidate:
        path = os.path.join(settings.fixtures_dir, "clip_1.mp4")
        return Candidate(
            source="mock-gen", id="gen-" + str(abs(hash(prompt)) % 10**8), url=path,
            licence="generated", attribution="AI-generated (mock)",
            commercial_ok=True, watermark=False, duration=6.0,
            width=640, height=360, ai_generated=True)


class MockJudge(Judge):
    def score(self, clip_path: str, narration: str) -> float:
        return 4.0