from app.config import settings
from app.providers.base import (ASRProvider, FootageProvider, GenerativeProvider,
                                Judge, LLMProvider, TTSProvider)
from app.providers.mock import (MockASR, MockFootage, MockGenerative, MockJudge,
                                MockLLM, MockTTS)

_REGISTRY = {
    "asr": {"mock": MockASR},
    "tts": {"mock": MockTTS},
    "llm": {"mock": MockLLM},
    "footage": {"mock": MockFootage},
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
    return _make("footage", settings.footage_provider)


def get_generative() -> GenerativeProvider:
    return _make("generative", "mock")


def get_judge() -> Judge:
    return _make("judge", "mock")