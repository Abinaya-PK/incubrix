import time

import httpx


class ProviderError(Exception):
    pass


def get_json(url: str, params=None, headers=None, retries: int = 2, timeout: float = 10.0) -> dict:
    last = None
    for attempt in range(retries + 1):
        try:
            r = httpx.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise ProviderError(f"HTTP {r.status_code}")
            if r.status_code >= 400:
                raise ProviderError(f"HTTP {r.status_code} (not retried)")
            return r.json()
        except ProviderError as e:
            last = e
            if "not retried" in str(e):
                break
        except (httpx.HTTPError, ValueError) as e:
            last = e
        time.sleep(0.5 * (2 ** attempt))
    raise ProviderError(f"{url}: {last}")