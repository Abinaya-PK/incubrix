import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.errors import ApiError

ALLOWED_EXT = {".mp3", ".wav", ".m4a"}
SILENCE_DB = -50.0
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: str) -> dict:
    r = _run(["ffprobe", "-v", "error", "-print_format", "json",
              "-show_format", "-show_streams", path])
    if r.returncode != 0:
        raise ApiError("UNSUPPORTED_MEDIA_TYPE", "File is not readable audio.", 415)
    info = json.loads(r.stdout or "{}")
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise ApiError("UNSUPPORTED_MEDIA_TYPE", "File has no audio stream.", 415)
    duration = float(info.get("format", {}).get("duration") or 0)
    return {"duration": duration, "codec": streams[0].get("codec_name")}


def validate(path: str) -> dict:
    ext = Path(path).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ApiError("UNSUPPORTED_MEDIA_TYPE",
                       f"Allowed audio types: {sorted(ALLOWED_EXT)}", 415,
                       details={"extension": ext})
    info = probe(path)
    if info["duration"] <= 0:
        raise ApiError("CORRUPT_AUDIO", "Audio has no duration.", 422)
    limit = settings.max_audio_minutes * 60
    if info["duration"] > limit:
        raise ApiError("AUDIO_TOO_LONG",
                       f"Audio is longer than {settings.max_audio_minutes} minutes.", 413,
                       details={"duration": info["duration"], "limit_seconds": limit})
    return info


def to_wav(src: str, dst: str) -> str:
    r = _run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", dst])
    if r.returncode != 0:
        raise ApiError("CORRUPT_AUDIO", "Audio could not be decoded.", 422)
    return dst


def is_silent(path: str) -> bool:
    r = _run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", r.stderr)
    return m is None or float(m.group(1)) < SILENCE_DB


def download_audio(url: str, dest_dir: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ApiError("INVALID_AUDIO_URL", "audio_url must start with http or https.", 400)
    ext = Path(parsed.path).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ApiError("UNSUPPORTED_MEDIA_TYPE",
                       f"Allowed audio types: {sorted(ALLOWED_EXT)}", 415)
    dest = str(Path(dest_dir) / f"input{ext}")
    try:
        size = 0
        with httpx.stream("GET", url, timeout=30, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise ApiError("AUDIO_TOO_LARGE", "Audio file is too large.", 413)
                    f.write(chunk)
    except ApiError:
        raise
    except Exception as e:
        raise ApiError("AUDIO_DOWNLOAD_FAILED", f"Could not download audio: {e}",
                       502, retryable=True)
    return dest


def prepare_audio(src: str, workdir: str) -> tuple[str, float]:
    """Validate, convert to 16 kHz mono WAV, reject silence. Returns (wav, seconds)."""
    validate(src)
    wav = to_wav(src, str(Path(workdir) / "narration.wav"))
    if is_silent(wav):
        raise ApiError("NO_SPEECH_DETECTED", "The audio is silent.", 422)
    return wav, probe(wav)["duration"]