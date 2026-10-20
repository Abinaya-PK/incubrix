import logging
from itertools import zip_longest

from app.providers.base import Candidate, FootageProvider
from app.providers.http import ProviderError

log = logging.getLogger("footage")


class MultiFootage(FootageProvider):
    name = "multi"

    def __init__(self, providers: list[FootageProvider]):
        self.providers = providers

    def search(self, query: str, min_duration: float = 0.0) -> list[Candidate]:
        lists, failures = [], 0
        for p in self.providers:
            try:
                lists.append(p.search(query, min_duration))
            except Exception as e:
                failures += 1
                log.warning("provider %s failed: %s", p.name, e)
        if failures == len(self.providers):
            raise ProviderError("all footage providers failed")
        mixed = [c for group in zip_longest(*lists) for c in group if c is not None]
        return mixed