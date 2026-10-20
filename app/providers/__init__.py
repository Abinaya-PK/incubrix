from app.config import settings
from app.providers.base import (ASRProvider, FootageProvider, GenerativeProvider,
                                Judge, LLMProvider, TTSProvider)
from app.providers.mock import (MockASR, MockFootage, MockGenerative, MockJudge,
                                MockLLM, MockTTS)
from app.providers.multi import MultiFootage
from app.providers.pexels import PexelsFootage
from app.providers.pixabay import PixabayFootage

_REGISTRY = {
    "asr": {"mock": MockASR},
    "tts": {"mock": MockTTS},
    "llm": {"mock": MockLLM},
    "footage": {"mock": MockFootage, "pexels": PexelsFootage, "pixabay": PixabayFootage},
    "generative": {"mock": MockGenerative},
    "judge": {"mock": MockJudge},
}


def _make(kind: str, name: str):
    try:
        return _REGISTRY[kind][name]()
    except KeyError:
        raise ValueError(f"Unknown {kind} provider '{name}'. "
                         f"Available: {list(_REGISTRY[kind])}")


def get_asr() -> ASRProvider:
    return _make("asr", settings.asr_provider)


def get_tts() -> TTSProvider:
    return _make("tts", settings.tts_provider)


def get_llm() -> LLMProvider:
    return _make("llm", settings.llm_provider)


def get_footage() -> FootageProvider:
    names = [n.strip() for n in settings.footage_provider.split(",") if n.strip()]
    if len(names) == 1:
        return _make("footage", names[0])
    return MultiFootage([_make("footage", n) for n in names])

def get_generative() -> GenerativeProvider:
    return _make("generative", "mock")


def get_judge() -> Judge:
    return _make("judge", "mock")