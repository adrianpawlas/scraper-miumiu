"""HTTP client with rate limiting and browser-like headers."""
import time
from typing import Optional

import httpx

from config import BASE_URL

# Act like a normal browser to reduce block risk
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Delay between requests (seconds)
REQUEST_DELAY = 1.5
LAST_REQUEST_TIME: float = 0


def _wait_rate_limit() -> None:
    global LAST_REQUEST_TIME
    elapsed = time.monotonic() - LAST_REQUEST_TIME
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    LAST_REQUEST_TIME = time.monotonic()


def get_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )


def get(url: str, client: Optional[httpx.Client] = None, **kwargs) -> httpx.Response:
    _wait_rate_limit()
    if client is not None:
        return client.get(url, **kwargs)
    with get_client() as c:
        return c.get(url, **kwargs)
