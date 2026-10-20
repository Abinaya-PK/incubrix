from app.config import settings
from app.providers.base import Candidate, FootageProvider
from app.providers.http import ProviderError, get_json


class PixabayFootage(FootageProvider):
    name = "pixabay"

    def search(self, query: str, min_duration: float = 0.0) -> list[Candidate]:
        if not settings.pixabay_api_key:
            raise ProviderError("PIXABAY_API_KEY is not set")
        data = get_json("https://pixabay.com/api/videos/",
                        params={"key": settings.pixabay_api_key, "q": query[:100],
                                "per_page": 20, "safesearch": "true"})
        out = []
        for h in data.get("hits", []):
            vids = h.get("videos", {})
            pick = next((vids[k] for k in ("large", "medium", "small")
                         if vids.get(k, {}).get("url")), None)
            if not pick or h.get("duration", 0) < min_duration:
                continue
            out.append(Candidate(
                source="pixabay", id=str(h["id"]), url=pick["url"],
                licence="Pixabay Content License",
                attribution=f"Video by {h.get('user', 'unknown')} on Pixabay",
                commercial_ok=True, watermark=False,
                duration=float(h["duration"]), width=pick["width"], height=pick["height"],
                page_url=h.get("pageURL", "")))
        return out