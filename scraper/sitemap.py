"""Discover product URLs from Miu Miu sitemap (avoids category page redirect issues)."""
import re
from typing import Iterator
from urllib.parse import urlparse

import httpx

from config import BASE_URL
from scraper.client import get, get_client


SITEMAP_INDEX_URLS = [
    f"{BASE_URL}/sitemap.xml",
    f"{BASE_URL}/sitemap_index_0.xml",
    f"{BASE_URL}/sitemap_index_1.xml",
]


def _extract_locs(xml: str) -> list[str]:
    """Extract <loc>URL</loc> from sitemap XML."""
    return re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml, re.IGNORECASE)


def _is_product_url(url: str) -> bool:
    return "/p/" in url and "miumiu.com" in url


def _is_sitemap_url(url: str) -> bool:
    return (
        "sitemap" in url.lower()
        and (url.endswith(".xml") or "sitemap" in urlparse(url).path)
        and "miumiu.com" in url
    )


def fetch_sitemap_product_urls(
    client: httpx.Client,
    max_sitemaps: int = 50,
) -> Iterator[str]:
    """
    Fetch sitemap index and child sitemaps; yield product URLs (links containing /p/).
    """
    seen_paths: set[str] = set()
    sitemaps_to_fetch = list(SITEMAP_INDEX_URLS)
    fetched = 0

    while sitemaps_to_fetch and fetched < max_sitemaps:
        url = sitemaps_to_fetch.pop(0)
        try:
            r = get(url, client=client)
            r.raise_for_status()
            xml = r.text
        except Exception:
            continue
        fetched += 1

        for loc in _extract_locs(xml):
            loc = loc.strip()
            if _is_product_url(loc):
                path = urlparse(loc).path
                if path not in seen_paths:
                    seen_paths.add(path)
                    yield loc
            elif _is_sitemap_url(loc) and loc not in sitemaps_to_fetch:
                sitemaps_to_fetch.append(loc)


def get_all_product_urls_from_sitemap(client: httpx.Client | None = None) -> list[str]:
    """Return list of all product URLs found via sitemap."""
    if client is None:
        with get_client() as c:
            return list(fetch_sitemap_product_urls(c))
    return list(fetch_sitemap_product_urls(client))
