"""
Supabase import via PostgREST REST API (no SDK).
Matches the approach used in other scrapers for reliable automated runs.
"""
import hashlib
import json
from typing import Any

import httpx

from config import DRY_RUN, SUPABASE_KEY, SUPABASE_URL

SOURCE = "miumiu"
CHUNK_SIZE = 100
REQUEST_TIMEOUT = 120


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _base_url() -> str:
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1"


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _format_product(parsed: dict[str, Any]) -> dict[str, Any]:
    """Convert parsed product to DB row. All products get same keys (None for missing)."""
    url = parsed.get("url") or ""
    product_code = parsed.get("product_code") or ""
    return {
        "id": hashlib.sha256(f"{SOURCE}:{url}".encode("utf-8")).hexdigest(),
        "source": SOURCE,
        "product_code": product_code,
        "product_url": url,
        "title": parsed.get("title"),
        "description": parsed.get("description"),
        "price": parsed.get("price"),
        "sale_price": parsed.get("sale_price"),
        "currency": parsed.get("currency") or "USD",
        "main_image": parsed.get("main_image"),
        "additional_images": parsed.get("additional_images") or [],
        "url": url,
        "category": parsed.get("category"),
        "categories": parsed.get("categories") or [],
        "attributes": parsed.get("attributes") or {},
        "raw_data": parsed.get("raw_data"),
    }


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure every row has the same keys (PostgREST requirement). Use None for missing."""
    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    return [{k: r.get(k) for k in all_keys} for r in rows]


def upsert_products(products: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Upsert products in batches via PostgREST.
    Returns (success_count, fail_count).
    """
    if DRY_RUN or not is_configured():
        return (len(products), 0) if is_configured() or DRY_RUN else (0, len(products))
    if not products:
        return (0, 0)

    rows = [_format_product(p) for p in products]
    normalized = _normalize_rows(rows)
    endpoint = f"{_base_url()}/products"
    post_headers = {**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}

    success = 0
    fail = 0
    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=_headers()) as client:
        for i in range(0, len(normalized), CHUNK_SIZE):
            chunk = normalized[i : i + CHUNK_SIZE]
            try:
                r = client.post(
                    endpoint,
                    headers=post_headers,
                    content=json.dumps(chunk, default=str),
                )
                if r.status_code in (200, 201, 204):
                    success += len(chunk)
                else:
                    print(f"Supabase upsert failed: {r.status_code} {r.text[:500]}")
                    fail += len(chunk)
                    for single in chunk:
                        try:
                            rr = client.post(endpoint, headers=post_headers, content=json.dumps([single], default=str))
                            if rr.status_code in (200, 201, 204):
                                success += 1
                                fail -= 1
                            else:
                                print(f"  Single retry failed: {rr.status_code}")
                        except Exception as e:
                            print(f"  Retry error: {e}")
            except Exception as e:
                print(f"Supabase batch error: {type(e).__name__}: {e}")
                fail += len(chunk)
    return (success, fail)


def delete_removed_from_catalog(scraped_product_codes: set[str]) -> tuple[int, str | None]:
    """
    Delete products that are in DB (source=miumiu) but not in this scrape (removed from catalog).
    Returns (deleted_count, error_message or None).
    """
    if DRY_RUN or not is_configured():
        return (0, None)
    if not scraped_product_codes:
        return (0, None)

    base = _base_url()
    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=_headers()) as client:
        try:
            r = client.get(
                f"{base}/products",
                params={"source": f"eq.{SOURCE}", "select": "product_code"},
                headers={"Range": "0-99999"},
            )
            if r.status_code != 200:
                return (0, f"GET existing failed: {r.status_code}")
            existing = [x.get("product_code") for x in r.json() if x.get("product_code")]
        except Exception as e:
            return (0, str(e))

        to_remove = [c for c in existing if c not in scraped_product_codes]
        if not to_remove:
            return (0, None)

        deleted = 0
        for i in range(0, len(to_remove), 100):
            batch = to_remove[i : i + 100]
            in_list = ",".join(batch)
            params = {"source": f"eq.{SOURCE}", "product_code": f"in.({in_list})"}
            try:
                rr = client.delete(f"{base}/products", params=params)
                if rr.status_code in (200, 204):
                    deleted += len(batch)
                else:
                    print(f"Supabase delete batch failed: {rr.status_code} {rr.text[:300]}")
            except Exception as e:
                print(f"Delete batch error: {e}")
        return (deleted, None)
