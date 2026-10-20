from app.config import settings
from app.providers.base import Candidate, FootageProvider
from app.providers.http import ProviderError, get_json


class PexelsFootage(FootageProvider):
    name = "pexels"

    def search(self, query: str, min_duration: float = 0.0) -> list[Candidate]:
        if not settings.pexels_api_key:
            raise ProviderError("PEXELS_API_KEY is not set")
        data = get_json("https://api.pexels.com/videos/search",
                        params={"query": query, "per_page": 15},
                        headers={"Authorization": settings.pexels_api_key})
        out = []
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and f.get("width") and f.get("link")]
            if not files or v.get("duration", 0) < min_duration:
                continue
            best = min(files, key=lambda f: abs(f["width"] - 1920))
            author = (v.get("user") or {}).get("name", "unknown")
            out.append(Candidate(
                source="pexels", id=str(v["id"]), url=best["link"],
                licence="Pexels License",
                attribution=f"Video by {author} on Pexels",
                commercial_ok=True, watermark=False,
                duration=float(v["duration"]), width=best["width"], height=best["height"],
                page_url=v.get("url", "")))
        return out