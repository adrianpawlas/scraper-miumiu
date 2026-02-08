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

# Fallback: /c/CODE URLs so we get pagination (page 2, 3...) even if .html doesn't link to them
# (Category codes from site structure; EU codes.)
FALLBACK_CATEGORY_CODES = [
    ("bags", "10268EU"),
    ("shoes", "10207EU"),
    ("ready-to-wear", "10216EU"),
    ("accessories", "10259EU"),
    ("new-arrivals", "10200EU"),
]

# Pagination: /eu/en/category/c/10207EU/page/2, /page/3, ...
PAGINATION_PATTERN = re.compile(r"/page/(\d+)$")


def _full_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return urljoin(BASE_URL + "/", path.lstrip("/"))


def _normalize_listing_url(url: str) -> str:
    """Strip trailing slash and default to page 1 for comparison."""
    url = url.rstrip("/")
    return url


def extract_category_links(html: str, base: str) -> list[str]:
    """From main or category page HTML, extract links that look like category listing pages."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    # View-all, /c/CODE, and /c/CODE/page/N
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href in seen:
            continue
        full = _full_url(href)
        if "miumiu.com" not in full or "/p/" in full:
            continue
        # Category listing: .../c/10207EU or .../c/10207EU/page/2 or /view-all/
        if "/view-all/" in href or re.search(r"/c/\d+[A-Z]*(?:/page/\d+)?$", href):
            key = _normalize_listing_url(full)
            if key not in seen:
                seen.add(key)
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
        path = urlparse(full).path
        if path in seen:
            continue
        seen.add(path)
        out.append(full)
    return out


def extract_pagination_links(html: str, current_url: str) -> list[str]:
    """Extract links to same category but other pages: .../c/CODE/page/2, /page/3, etc."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    current_path = urlparse(current_url).path.rstrip("/")
    # Base path without /page/N (e.g. /eu/en/shoes/c/10207EU)
    base_path = PAGINATION_PATTERN.sub("", current_path).rstrip("/") or current_path
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full = _full_url(href)
        if "miumiu.com" not in full or "/p/" in full:
            continue
        path = urlparse(full).path.rstrip("/")
        if PAGINATION_PATTERN.search(path) and path.startswith(base_path):
            if path not in seen:
                seen.add(path)
                out.append(full)
    return out


def discover_category_urls(client: httpx.Client) -> list[str]:
    """Return list of category listing URLs (default + fallback /c/CODE for pagination + any from homepage)."""
    categories = list(DEFAULT_CATEGORY_PATHS)
    for _name, code in FALLBACK_CATEGORY_CODES:
        categories.append(f"{SITE_PREFIX}/{_name}/c/{code}")
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


# Cap listing pages to avoid runaway discovery (safety limit).
MAX_LISTING_PAGES = 300


def iter_product_urls_from_categories(
    client: httpx.Client,
    category_urls: list[str] | None = None,
) -> Iterator[str]:
    """Yield product page URLs from category pages, following pagination (/page/2, ...) and subcategory /c/CODE links."""
    if category_urls is None:
        category_urls = discover_category_urls(client)
    seen_products: set[str] = set()
    seen_listing_urls: set[str] = set()
    to_fetch: list[str] = list(category_urls)
    fetched = 0

    while to_fetch and fetched < MAX_LISTING_PAGES:
        url = to_fetch.pop(0)
        norm = _normalize_listing_url(url)
        if norm in seen_listing_urls:
            continue
        seen_listing_urls.add(norm)
        fetched += 1
        try:
            r = get(url, client=client)
            r.raise_for_status()
            html = r.text
        except Exception:
            continue

        for product_url in extract_product_links(html, url):
            path = urlparse(product_url).path
            if path not in seen_products:
                seen_products.add(path)
                yield product_url

        for pagination_url in extract_pagination_links(html, url):
            norm_p = _normalize_listing_url(pagination_url)
            if norm_p not in seen_listing_urls:
                to_fetch.append(pagination_url)

        for subcat_url in extract_category_links(html, url):
            norm_s = _normalize_listing_url(subcat_url)
            if norm_s not in seen_listing_urls:
                to_fetch.append(subcat_url)
