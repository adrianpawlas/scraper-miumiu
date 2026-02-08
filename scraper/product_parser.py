"""Extract full product data from Miu Miu product page HTML (embedded JSON)."""
import json
import re
from typing import Any
from urllib.parse import urljoin

from config import BASE_URL


def _extract_product_json(html: str) -> dict[str, Any] | None:
    """Find the main product JSON blob in the page (contains 'attachments', 'fullImage', 'price')."""
    # The JSON is usually on one long line. Look for {"attachments":[ or "fullImage":" and grab the object.
    patterns = [
        r'(\{"attachments":\s*\[.*?"uniqueID"\s*:\s*"[^"]+"\s*,\s*"auraEnabled")',
        r'(\{"attachments":\s*\[.*?"formattedPrice"\s*:\s*"[^"]*")',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            raw = m.group(1)
            # May be truncated; try to close braces and parse
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
            # Try to find the end of the object (match braces)
            depth = 0
            end = 0
            for i, c in enumerate(raw):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                try:
                    return json.loads(raw[:end])
                except json.JSONDecodeError:
                    pass
    # Fallback: find object containing "fullImage"
    idx = html.find('"fullImage"')
    if idx == -1:
        return None
    # Prefer "{" that starts the product object (rfind returns index of "{")
    start = html.rfind('{"attachments"', max(0, idx - 600000), idx)
    if start == -1:
        start = html.rfind("{", max(0, idx - 600000), idx)
    if start == -1:
        start = html.rfind("{", 0, idx)
    if start == -1:
        return None
    depth = 0
    end = -1
    # Product JSON can be 600k+ chars; scan up to 1.5M
    for i in range(start, min(start + 1_500_000, len(html))):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        obj = json.loads(html[start:end])
        if isinstance(obj, dict) and ("fullImage" in obj or "attachments" in obj):
            return obj
    except json.JSONDecodeError:
        pass
    return None


def _price_value(price_list: list[dict] | None) -> tuple[float | None, float | None, str]:
    """Return (price, sale_price, currency) from product price array."""
    if not price_list:
        return (None, None, "USD")
    display = None
    offer = None
    currency = "USD"
    for p in price_list:
        if not isinstance(p, dict):
            continue
        val = p.get("value")
        try:
            num = float(val) if val is not None else None
        except (TypeError, ValueError):
            num = None
        fmt = (p.get("formattedPrice") or "") or ""
        if "€" in fmt:
            currency = "EUR"
        elif "£" in fmt:
            currency = "GBP"
        elif "$" in fmt or "USD" in fmt.upper():
            currency = "USD"
        usage = (p.get("usage") or "").upper()
        if usage == "DISPLAY" or usage == "L":
            display = num
        elif usage == "OFFER" or usage == "O":
            offer = num
    sale = offer if (display is not None and offer is not None and offer < display) else None
    main = display if display is not None else offer
    return (main, sale, currency)


def _images(data: dict) -> tuple[str | None, list[str]]:
    """Extract main image URL and list of additional image URLs."""
    main = data.get("fullImage") or data.get("thumbnail")
    if main and not main.startswith("http"):
        main = urljoin(BASE_URL + "/", main)
    additional: list[str] = []
    for att in data.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        path = att.get("attachmentAssetPath")
        if path:
            if not path.startswith("http"):
                path = urljoin(BASE_URL + "/", path)
            if path != main and path not in additional:
                additional.append(path)
    if main and main not in additional:
        pass  # keep main separate
    return (main, additional)


def _attributes_map(data: dict) -> dict[str, Any]:
    """Build a flat map of attribute name -> value(s) for storage."""
    out: dict[str, Any] = {}
    for attr in data.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        name = attr.get("name") or attr.get("identifier")
        vals = attr.get("values") or []
        if name:
            if len(vals) == 1 and isinstance(vals[0], dict):
                out[name] = vals[0].get("value") or vals[0].get("identifier")
            else:
                out[name] = [v.get("value") or v.get("identifier") for v in vals if isinstance(v, dict)]
    return out


def _categories_from_hierarchy(data: dict, page_url: str) -> tuple[str | None, list[str]]:
    """Category string and breadcrumb list."""
    hierarchy = data.get("Hierarchy") or data.get("hierarchy") or {}
    labels = hierarchy.get("Label") if isinstance(hierarchy, dict) else None
    if isinstance(labels, dict):
        # e.g. {"en_GB": ["BAG LINES", "UTILITAIRE"], "ww": [...]}
        for key, arr in labels.items():
            if isinstance(arr, list) and arr:
                return (arr[-1] if arr else None, list(arr))
    if isinstance(labels, list) and labels:
        return (labels[-1], list(labels))
    # Fallback from URL: /us/en/bags/view-all -> category "bags"
    path = page_url.split("/")
    for i, seg in enumerate(path):
        if seg in ("bags", "shoes", "ready-to-wear", "accessories", "wallets", "fashion-jewellery", "gifts"):
            return (seg, [seg])
    return (None, [])


def parse_product_page(html: str, page_url: str) -> dict[str, Any] | None:
    """
    Parse product page HTML and return a single dict suitable for Supabase/JSON.
    Keys: product_code, title, description, price, sale_price, currency, main_image,
    additional_images, url, category, categories, attributes, raw_data, short_description, etc.
    """
    data = _extract_product_json(html)
    if not data:
        return None

    product_code = data.get("partNumber") or data.get("uniqueID") or data.get("mfPartNumber_ntk") or ""
    if not product_code:
        return None

    main_image, additional_images = _images(data)
    price, sale_price, currency = _price_value(data.get("price"))

    title = data.get("name") or ""
    long_desc = data.get("longdescription") or ""
    short_desc = data.get("shortDescription") or ""
    description = long_desc or short_desc
    if short_desc and long_desc and short_desc != long_desc:
        description = long_desc + "\n\n" + short_desc.replace("---", "\n")

    category, categories_list = _categories_from_hierarchy(data, page_url)
    attributes = _attributes_map(data)

    return {
        "product_code": product_code,
        "title": title,
        "description": description or None,
        "short_description": short_desc or None,
        "price": price,
        "sale_price": sale_price,
        "currency": currency,
        "main_image": main_image,
        "additional_images": additional_images,
        "url": page_url,
        "category": category,
        "categories": categories_list,
        "attributes": attributes,
        "colors": data.get("colors"),
        "formatted_price": data.get("formattedPrice"),
        "life_cycle": data.get("lifeCycle"),
        "on_sale": data.get("onSale"),
        "other_variants": data.get("otherVariants") or data.get("colorVariants") or [],
        "size_codes": data.get("sizeCodes") or [],
        "skus": data.get("SKUs") or [],
        "raw_data": data,
    }
