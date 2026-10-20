import time
from dataclasses import asdict
from pathlib import Path

from app.config import settings
from app.errors import ApiError
from app.pipeline.audio import download_audio, prepare_audio
from app.pipeline.inputs import text_from_scenes, words_from_text
from app.pipeline.segment import segment
from app.providers import get_asr, get_footage, get_generative, get_judge, get_llm


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


def run_pipeline(req: dict, workdir: str, progress=lambda pct, msg="": None) -> dict:
    t0 = time.perf_counter()
    timings, warnings = {}, []

    progress(10, "reading input")
    words, seconds, hints = _load_words(req, workdir)
    timings["input_s"] = round(time.perf_counter() - t0, 3)

    scenes = segment(words, seconds, settings.min_scene_seconds, settings.max_scene_seconds)
    if not scenes:
        raise ApiError("NO_SPEECH_DETECTED", "No speech found in the input.", 422)

    llm, footage, generative, judge = get_llm(), get_footage(), get_generative(), get_judge()
    used: set[str] = set()
    out_scenes, offset = [], 0

    for i, sc in enumerate(scenes):
        progress(10 + int(80 * i / len(scenes)), f"scene {i + 1}/{len(scenes)}")
        hint = _scene_hint(hints, offset, len(sc.words))
        offset += len(sc.words)
        analysis = llm.analyze_scene(sc.text, visual_hint=hint, avoid=req.get("avoid"))
        scene_warnings = list(analysis.get("warnings", []))

        chosen, reason = None, ""
        for q in analysis["queries"]:
            for c in footage.search(q):
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

        out_scenes.append({
            "index": sc.index, "text": sc.text,
            "start": sc.start, "end": sc.end, "duration": round(sc.duration, 3),
            "visual_hint": hint, "queries": analysis["queries"],
            "clip": asdict(chosen),
            "reason": reason,
            "relevance_score": judge.score(chosen.url, sc.text),
            "warnings": scene_warnings,
        })
        warnings.extend(f"scene {i}: {w}" for w in scene_warnings)

    timings["total_s"] = round(time.perf_counter() - t0, 3)
    timeline = {"audio_seconds": round(seconds, 3), "scenes": out_scenes}
    manifest = {
        "providers": {"asr": settings.asr_provider, "tts": settings.tts_provider,
                      "llm": settings.llm_provider, "footage": settings.footage_provider},
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