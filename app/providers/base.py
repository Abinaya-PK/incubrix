from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Candidate:
    source: str
    id: str
    url: str  # local path or http link
    licence: str
    attribution: str
    commercial_ok: bool
    watermark: bool
    duration: float
    width: int
    height: int
    ai_generated: bool = False
    page_url: str = ""


class ASRProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, text_hint: str | None = None) -> list[Word]:
        """Return words with start/end times in seconds."""

class TTSProvider(ABC):
    @abstractmethod
    def speak(self, text: str, voice: str, out_path: str) -> str:
        """Write narration audio to out_path and return the path."""


class LLMProvider(ABC):
    @abstractmethod
    def analyze_scene(self, text: str, visual_hint: str | None = None,
                      avoid: list[str] | None = None) -> dict:
        """Return search queries, sense, abstract flag, warnings."""


class FootageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, min_duration: float = 0.0) -> list[Candidate]:
        """Return candidate clips with licence info."""


class GenerativeProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, duration: float) -> Candidate:
        """Return an AI-generated clip (ai_generated=True)."""


class Judge(ABC):
    @abstractmethod
    def score(self, clip_path: str, narration: str) -> float:
        """Return relevance from 1 to 5."""