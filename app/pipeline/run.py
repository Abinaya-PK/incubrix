import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.errors import ApiError
from app.pipeline.audio import download_audio, prepare_audio
from app.pipeline.inputs import text_from_scenes, words_from_text
from app.pipeline.segment import segment
from app.providers import (get_asr, get_footage, get_generative,
                           get_image_provider, get_judge, get_llm)
from app.providers.http import ProviderError


def _load_words(req: dict, workdir: str):
    """Return (words, audio_seconds, hints_per_word_or_None)."""
    if req.get("audio_url"):
        src = download_audio(req["audio_url"], workdir)
        wav, seconds = prepare_audio(src, workdir)
        return get_asr().transcribe(wav), seconds, None
    if req.get("scenes"):
        text, hints = text_from_scenes(req["scenes"])
        words, _, seconds = words_from_text(text, req.get("voice", ""), workdir)
        return words, seconds, hints if len(hints) == len(words) else None
    words, _, seconds = words_from_text(req.get("script") or "", req.get("voice", ""), workdir)
    return words, seconds, None


def _scene_hint(hints, offset: int, count: int):
    if not hints:
        return None
    return next((h for h in hints[offset:offset + count] if h), None)

def _safe_search(footage, query, scene_warnings):
    try:
        return footage.search(query)
    except Exception as e:
        scene_warnings.append(f"footage search failed for '{query}': {e}")
        return []

def run_pipeline(req: dict, workdir: str, progress=lambda pct, msg="": None,
                 output_id: str | None = None) -> dict:
    t0 = time.perf_counter()
    timings, warnings = {}, []

    progress(10, "reading input")
    words, seconds, hints = _load_words(req, workdir)
    timings["input_s"] = round(time.perf_counter() - t0, 3)

    scenes = segment(words, seconds, settings.min_scene_seconds, settings.max_scene_seconds)
    if not scenes:
        raise ApiError("NO_SPEECH_DETECTED", "No speech found in the input.", 422)

    llm, footage, generative, image_provider, judge = (
        get_llm(), get_footage(), get_generative(), get_image_provider(), get_judge()
    )
    used: set[str] = set()
    out_scenes, offset = [], 0
    image_job_id = output_id or uuid4().hex
    image_dir = Path(settings.image_output_dir) / image_job_id
    try:
        image_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ApiError("IMAGE_STORAGE_FAILED", str(exc), 500, retryable=True) from exc

    for i, sc in enumerate(scenes):
        progress(10 + int(80 * i / len(scenes)), f"scene {i + 1}/{len(scenes)}")
        hint = _scene_hint(hints, offset, len(sc.words))
        offset += len(sc.words)
        analysis = llm.analyze_scene(sc.text, visual_hint=hint, avoid=req.get("avoid"))
        scene_warnings = list(analysis.get("warnings", []))

        chosen, reason = None, ""
        for q in analysis["queries"]:
            for c in _safe_search(footage, q, scene_warnings):
                key = f"{c.source}:{c.id}"
                if c.commercial_ok and not c.watermark and key not in used:
                    chosen, reason = c, f"stock: first licence-clean unused match for '{q}'"
                    break
            if chosen:
                break

        if chosen is None:
            chosen = generative.generate(analysis["queries"][0], sc.duration)
            reason = "generated: no unused licence-clean stock clip was found"
            scene_warnings.append("fallback to AI-generated clip")
        used.add(f"{chosen.source}:{chosen.id}")

        if chosen.duration < sc.duration:
            scene_warnings.append("clip shorter than scene; will be slowed or extended at render time")

        image_prompt = [f"Scene narration: {sc.text}"]
        if hint:
            image_prompt.append(f"Visual direction: {hint}")
        if req.get("style"):
            image_prompt.append(f"Style: {req['style']}")
        if req.get("avoid"):
            image_prompt.append(f"Avoid: {', '.join(req['avoid'])}")

        try:
            generated_image = image_provider.generate(
                "\n".join(image_prompt), aspect_ratio="16:9"
            )
        except ProviderError as exc:
            raise ApiError("IMAGE_GENERATION_FAILED", str(exc), 502, retryable=True) from exc

        image_path = image_dir / f"scene_{sc.index:03d}.png"
        try:
            image_path.write_bytes(generated_image.data)
        except OSError as exc:
            raise ApiError("IMAGE_STORAGE_FAILED", str(exc), 500, retryable=True) from exc
        try:
            image_reference = image_path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            image_reference = str(image_path)

        out_scenes.append({
            "index": sc.index, "text": sc.text,
            "start": sc.start, "end": sc.end, "duration": round(sc.duration, 3),
            "visual_hint": hint, "queries": analysis["queries"],
            "clip": asdict(chosen),
            "image": {
                "path": image_reference,
                "provider": generated_image.provider,
                "mime_type": generated_image.mime_type,
                "width": generated_image.width,
                "height": generated_image.height,
            },
            "reason": reason,
            "relevance_score": judge.score(chosen.url, sc.text),
            "warnings": scene_warnings,
        })
        warnings.extend(f"scene {i}: {w}" for w in scene_warnings)

    timings["total_s"] = round(time.perf_counter() - t0, 3)
    timeline = {"audio_seconds": round(seconds, 3), "scenes": out_scenes}
    manifest = {
        "providers": {"asr": settings.asr_provider, "tts": settings.tts_provider,
                      "llm": settings.llm_provider, "footage": settings.footage_provider,
                      "image": settings.image_provider},
        "settings": {"min_scene_seconds": settings.min_scene_seconds,
                     "max_scene_seconds": settings.max_scene_seconds,
                     "aspect_ratios": req.get("aspect_ratios"), "style": req.get("style"),
                     "avoid": req.get("avoid")},
        "timings": timings,
        "cost_estimate_usd": 0.0,
        "warnings": warnings,
        "rights": {"all_commercial_ok": all(s["clip"]["commercial_ok"] for s in out_scenes),
                   "ai_generated_scenes": [s["index"] for s in out_scenes
                                           if s["clip"]["ai_generated"]]},
    }
    progress(95, "writing outputs")
    return {"timeline": timeline, "manifest": manifest}