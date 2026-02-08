"""Upsert product rows into Supabase."""
from typing import Any

from config import DRY_RUN, SUPABASE_KEY, SUPABASE_URL


def is_configured() -> bool:
    """Return True if Supabase URL and key are set (and non-empty)."""
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _client():
    if not is_configured():
        return None
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None


def _row_for_supabase(product: dict[str, Any]) -> dict[str, Any]:
    """Map our product dict to table columns (title, description, prices, main_image, additional_images, etc.)."""
    return {
        "product_code": product.get("product_code"),
        "title": product.get("title"),
        "description": product.get("description"),
        "price": product.get("price"),
        "sale_price": product.get("sale_price"),
        "currency": product.get("currency") or "USD",
        "main_image": product.get("main_image"),
        "additional_images": product.get("additional_images") or [],
        "url": product.get("url"),
        "category": product.get("category"),
        "categories": product.get("categories") or [],
        "attributes": product.get("attributes") or {},
        "raw_data": product.get("raw_data"),
        "updated_at": "now()",
    }


def upsert_product(product: dict[str, Any]) -> bool:
    """Insert or update one product. Returns True if successful (or DRY_RUN)."""
    if DRY_RUN:
        return True
    client = _client()
    if not client:
        return False
    row = _row_for_supabase(product)
    # Don't send updated_at as "now()" string; let DB default handle it, or set in SQL
    row.pop("updated_at", None)
    try:
        client.table("products").upsert(
            row,
            on_conflict="product_code",
            ignore_duplicates=False,
        ).execute()
        return True
    except Exception:
        return False


def upsert_products(products: list[dict[str, Any]]) -> tuple[int, int]:
    """Upsert many products. Returns (success_count, fail_count)."""
    ok = 0
    fail = 0
    for p in products:
        if upsert_product(p):
            ok += 1
        else:
            fail += 1
    return (ok, fail)
