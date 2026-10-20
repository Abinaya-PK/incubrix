import logging

from app.config import settings
from app.providers.base import ASRProvider, Word

log = logging.getLogger("asr")
_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel   # imported lazily: heavy
        log.info("loading whisper model %s", settings.whisper_model)
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            download_root=settings.model_cache_dir,
        )
    return _model


class WhisperASR(ASRProvider):
    def transcribe(self, audio_path: str, text_hint: str | None = None) -> list[Word]:
        segments, info = _get_model().transcribe(
            audio_path,
            word_timestamps=True,
            vad_filter=True,
            language=settings.whisper_language or None,
        )
        words = []
        for seg in segments:
            for w in seg.words or []:
                text = w.word.strip()
                if text:
                    words.append(Word(text, round(w.start, 3), round(w.end, 3)))
        log.info("transcribed %d words, language=%s", len(words), info.language)
        return words