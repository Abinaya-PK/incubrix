import base64
import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.config import settings
from app.pipeline.run import run_pipeline
from app.providers import images
from app.providers.http import ProviderError


def png_bytes(size):
    output = io.BytesIO()
    Image.new("RGB", size, color=(20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def test_openai_provider_requests_preferred_landscape_and_crops_to_16_9(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    request_data = {}

    def fake_post(url, headers, json, timeout):
        request_data.update(url=url, headers=headers, json=json, timeout=timeout)
        body = {"data": [{"b64_json": base64.b64encode(png_bytes((1536, 1024))).decode()}]}
        return httpx.Response(
            200, json=body, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(images.httpx, "post", fake_post)
    generated = images.OpenAIImageProvider().generate("coins in a jar")

    assert request_data["json"]["size"] == "1536x1024"
    assert request_data["json"]["model"] == settings.openai_image_model
    assert "coins in a jar" in request_data["json"]["prompt"]
    assert request_data["headers"]["Authorization"] == "Bearer test-key"
    assert (generated.width, generated.height) == (1536, 864)
    with Image.open(io.BytesIO(generated.data)) as image:
        assert image.size == (1536, 864)


def test_openai_provider_requires_credentials(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        images.OpenAIImageProvider().generate("a visual")


def test_pipeline_saves_one_image_per_scene_with_scene_context(tmp_path, monkeypatch):
    prompts = []

    class RecordingImageProvider:
        def generate(self, prompt, aspect_ratio="16:9"):
            prompts.append((prompt, aspect_ratio))
            return images.MockImageProvider().generate(prompt, aspect_ratio)

    monkeypatch.setattr(
        "app.pipeline.run.get_image_provider", lambda: RecordingImageProvider()
    )
    output = run_pipeline(
        {
            "scenes": [{"text": "Save money.", "visual_hint": "coins in a jar"}],
            "style": "warm documentary",
            "avoid": ["logos"],
        },
        str(tmp_path),
        output_id="test-job",
    )
    scenes = output["timeline"]["scenes"]

    assert len(scenes) == 1
    assert "Save money." in prompts[0][0]
    assert "coins in a jar" in prompts[0][0]
    assert "warm documentary" in prompts[0][0]
    assert "logos" in prompts[0][0]
    assert prompts[0][1] == "16:9"
    for scene in scenes:
        image = scene["image"]
        path = Path(image["path"])
        assert path.is_file()
        assert image["mime_type"] == "image/png"
        assert image["provider"] == "mock"
        assert image["width"] == 16
        assert image["height"] == 9
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert len({scene["image"]["path"] for scene in scenes}) == len(scenes)
