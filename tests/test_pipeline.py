import pytest

from app.config import settings
from app.errors import ApiError
from app.pipeline.run import run_pipeline

SCRIPT = ("Saving money is easy for everyone. Plan ahead and track every expense. "
          "Small habits add up over time. Review your budget each month. "
          "Celebrate every goal you reach.")


@pytest.fixture(autouse=True)
def short_scenes(monkeypatch):
    monkeypatch.setattr(settings, "min_scene_seconds", 1.0)


def test_timeline_is_complete_and_contiguous(tmp_path):
    out = run_pipeline({"script": SCRIPT, "aspect_ratios": ["16:9"]}, str(tmp_path))
    scenes = out["timeline"]["scenes"]
    assert len(scenes) >= 4
    assert scenes[0]["start"] == 0.0
    assert scenes[-1]["end"] == out["timeline"]["audio_seconds"]
    assert all(a["end"] == b["start"] for a, b in zip(scenes, scenes[1:]))


def test_no_clip_repeats_and_all_licensed(tmp_path):
    out = run_pipeline({"script": SCRIPT}, str(tmp_path))
    clips = [(s["clip"]["source"], s["clip"]["id"]) for s in out["timeline"]["scenes"]]
    assert len(clips) == len(set(clips))
    assert all(s["clip"]["commercial_ok"] for s in out["timeline"]["scenes"])
    assert out["manifest"]["rights"]["all_commercial_ok"]


def test_fallback_is_flagged_when_stock_runs_out(tmp_path):
    out = run_pipeline({"script": SCRIPT}, str(tmp_path))   # only 3 mock clips
    gen = [s for s in out["timeline"]["scenes"] if s["clip"]["ai_generated"]]
    assert gen and all("fallback" in " ".join(s["warnings"]) for s in gen)
    assert out["manifest"]["rights"]["ai_generated_scenes"] == [s["index"] for s in gen]


def test_scene_list_hint_is_used(tmp_path):
    req = {"scenes": [{"text": "Save money every month.", "visual_hint": "coins in a jar"},
                      {"text": "Track what you spend.", "visual_hint": "person using a phone"}]}
    out = run_pipeline(req, str(tmp_path))
    assert out["timeline"]["scenes"][0]["visual_hint"] == "coins in a jar"


def test_empty_script_rejected(tmp_path):
    with pytest.raises(ApiError) as e:
        run_pipeline({"script": "  "}, str(tmp_path))
    assert e.value.code == "EMPTY_INPUT"