import base64
import io

import httpx
from PIL import Image

from app.config import settings
from app.providers.base import GeneratedImage, ImageProvider
from app.providers.http import ProviderError

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_LANDSCAPE_SIZE = "1536x1024"


def _to_landscape_16_9(data: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            target_height = round(width * 9 / 16)
            if height > target_height:
                top = (height - target_height) // 2
                image = image.crop((0, top, width, top + target_height))
            elif height < target_height:
                target_width = round(height * 16 / 9)
                left = (width - target_width) // 2
                image = image.crop((left, 0, left + target_width, height))
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG")
            return output.getvalue(), image.width, image.height
    except (OSError, ValueError) as exc:
        raise ProviderError(f"image provider returned invalid image data: {exc}") from exc


class OpenAIImageProvider(ImageProvider):
    def generate(self, prompt: str, aspect_ratio: str = "16:9") -> GeneratedImage:
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        if aspect_ratio != "16:9":
            raise ProviderError(f"unsupported image aspect ratio: {aspect_ratio}")

        full_prompt = (
            f"{prompt}\n\n"
            "Create a cinematic B-roll still for a 16:9 video. Compose the important "
            "subjects safely within a centered 16:9 crop."
        )
        try:
            response = httpx.post(
                OPENAI_IMAGES_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_image_model,
                    "prompt": full_prompt,
                    "size": OPENAI_LANDSCAPE_SIZE,
                    "output_format": "png",
                },
                timeout=120.0,
            )
            response.raise_for_status()
            response_data = response.json()
            encoded_image = response_data["data"][0]["b64_json"]
            source_data = base64.b64decode(encoded_image, validate=True)
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"OpenAI image generation failed with HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"OpenAI image generation failed: {exc}") from exc

        image_data, width, height = _to_landscape_16_9(source_data)
        return GeneratedImage(image_data, "openai", width, height)


class MockImageProvider(ImageProvider):
    def generate(self, prompt: str, aspect_ratio: str = "16:9") -> GeneratedImage:
        if aspect_ratio != "16:9":
            raise ProviderError(f"unsupported image aspect ratio: {aspect_ratio}")
        image = Image.new("RGB", (16, 9), color=(128, 128, 128))
        output = io.BytesIO()
        image.save(output, format="PNG")
        return GeneratedImage(output.getvalue(), "mock", image.width, image.height)
