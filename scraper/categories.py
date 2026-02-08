"""Discover category and product listing URLs from Miu Miu site."""
import re
from typing import Iterator
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config import BASE_URL, SITE_PREFIX
from scraper.client import get, get_client


# Category listing pages (.html works; /view-all/c/default can redirect-loop on some networks)
DEFAULT_CATEGORY_PATHS = [
    f"{SITE_PREFIX}/bags.html",
    f"{SITE_PREFIX}/shoes.html",
    f"{SITE_PREFIX}/ready-to-wear.html",
    f"{SITE_PREFIX}/accessories.html",
    f"{SITE_PREFIX}/wallets.html",
    f"{SITE_PREFIX}/fashion-jewellery.html",
    f"{SITE_PREFIX}/gifts.html",
    f"{SITE_PREFIX}/new-arrivals.html",
]


def _full_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return urljoin(BASE_URL + "/", path.lstrip("/"))


def extract_category_links(html: str, base: str) -> list[str]:
    """From main or category page HTML, extract links that look like category listing pages."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    # View-all and /c/ default category URLs
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href in seen:
            continue
        # Normalize: we want /country/market/category/view-all/c/default or .../c/CODE
        if "/view-all/" in href or re.search(r"/c/\d+[A-Z]*$", href):
            full = _full_url(href)
            if "miumiu.com" in full and "/p/" not in full:
                seen.add(href)
                out.append(full)
    return list(dict.fromkeys(out))  # preserve order, dedupe


def extract_product_links(html: str, page_url: str) -> list[str]:
    """From a category/listing page, extract product page URLs (/p/product-name/code)."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or "/p/" not in href:
            continue
        full = _full_url(href)
        if "miumiu.com" not in full:
            continue
        # Normalize: one URL per product (use path as key to avoid duplicate codes with different query params)
        path = urlparse(full).path
        if path in seen:
            continue
        seen.add(path)
        out.append(full)
    return out


def discover_category_urls(client: httpx.Client) -> list[str]:
    """Return list of category listing URLs (default + any from homepage)."""
    categories = list(DEFAULT_CATEGORY_PATHS)
    try:
        r = get(SITE_PREFIX + "/.html" if not SITE_PREFIX.endswith(".html") else SITE_PREFIX, client=client)
        r.raise_for_status()
        found = extract_category_links(r.text, r.url)
        for url in found:
            if url not in categories:
                categories.append(url)
    except Exception:
        pass
    return [_full_url(p) for p in categories]


def iter_product_urls_from_categories(
    client: httpx.Client,
    category_urls: list[str] | None = None,
) -> Iterator[str]:
    """Yield product page URLs from category pages. Pagination: same path with ?q=:page or page parameter if present."""
    if category_urls is None:
        category_urls = discover_category_urls(client)
    seen: set[str] = set()
    for cat_url in category_urls:
        try:
            r = get(cat_url, client=client)
            r.raise_for_status()
            for product_url in extract_product_links(r.text, cat_url):
                path = urlparse(product_url).path
                if path not in seen:
                    seen.add(path)
                    yield product_url
            # TODO: if page has "next" link, follow it for pagination
        except Exception:
            continue
