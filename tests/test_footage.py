import pytest

from app.config import settings
from app.providers import get_footage
from app.providers import pexels, pixabay
from app.providers.base import FootageProvider
from app.providers.http import ProviderError
from app.providers.multi import MultiFootage


def test_pexels_parsing(monkeypatch):
    monkeypatch.setattr(settings, "pexels_api_key", "x")
    monkeypatch.setattr(pexels, "get_json", lambda *a, **k: {"videos": [{
        "id": 1, "url": "https://www.pexels.com/video/1/", "duration": 10,
        "user": {"name": "Ann"},
        "video_files": [
            {"file_type": "video/mp4", "width": 640, "height": 360, "link": "https://x/360.mp4"},
            {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://x/1080.mp4"}]}]})
    c = pexels.PexelsFootage().search("money")[0]
    assert c.url == "https://x/1080.mp4"
    assert c.commercial_ok and not c.watermark and "Pexels" in c.licence
    assert "Ann" in c.attribution


def test_pixabay_parsing_skips_empty_large(monkeypatch):
    monkeypatch.setattr(settings, "pixabay_api_key", "x")
    monkeypatch.setattr(pixabay, "get_json", lambda *a, **k: {"hits": [{
        "id": 9, "pageURL": "https://pixabay.com/videos/id-9/", "user": "Bob", "duration": 8,
        "videos": {"large": {"url": "", "width": 0, "height": 0},
                   "medium": {"url": "https://y/m.mp4", "width": 1280, "height": 720}}}]})
    c = pixabay.PixabayFootage().search("money")[0]
    assert c.url == "https://y/m.mp4" and c.page_url.endswith("id-9/")


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "pexels_api_key", "")
    with pytest.raises(ProviderError):
        pexels.PexelsFootage().search("money")


class Down(FootageProvider):
    name = "down"

    def search(self, query, min_duration=0.0):
        raise ProviderError("simulated outage")


def test_multi_survives_one_provider_down():
    mixed = MultiFootage([Down(), get_footage()]).search("money")
    assert len(mixed) >= 3


def test_multi_all_down_raises():
    with pytest.raises(ProviderError):
        MultiFootage([Down(), Down()]).search("money")


def test_pipeline_survives_total_outage(tmp_path, monkeypatch):
    from app.pipeline import run
    monkeypatch.setattr(run, "get_footage", lambda: MultiFootage([Down()]))
    out = run.run_pipeline({"script": "Saving money is easy for everyone."}, str(tmp_path))
    scene = out["timeline"]["scenes"][0]
    assert scene["clip"]["ai_generated"] is True
    assert any("footage search failed" in w for w in scene["warnings"])