"""
Miu Miu full catalog scraper: discovers categories, fetches every product page,
extracts title, description, prices, main image, additional images, and all other
fields, then saves to JSON and upserts to Supabase.
"""
import json
import sys
from pathlib import Path

from config import DRY_RUN, LIMIT, SITE_PREFIX
from scraper.categories import discover_category_urls, iter_product_urls_from_categories
from scraper.client import get_client, get
from scraper.product_parser import parse_product_page
from scraper.supabase_client import is_configured, upsert_product


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    products_file = output_dir / "products.jsonl"
    failed_urls_file = output_dir / "failed_urls.txt"

    base_url = f"https://www.miumiu.com{SITE_PREFIX}"
    print("Miu Miu scraper — scraping everything for Supabase")
    print("Base:", base_url)
    if DRY_RUN:
        print("DRY_RUN=1: only saving JSON, no Supabase upload")
    if not DRY_RUN and not is_configured():
        print("WARNING: SUPABASE_URL and/or SUPABASE_KEY not set — products will NOT be written to the database.")
        print("         Set them in .env (local) or in GitHub Actions -> Settings -> Secrets (Actions).")
    print()

    with get_client() as client:
        # Discover product URLs from category listing pages (.html)
        print("Discovering product URLs from category pages...")
        category_urls = discover_category_urls(client)
        product_urls = list(iter_product_urls_from_categories(client, category_urls))

        if LIMIT > 0:
            product_urls = product_urls[:LIMIT]
            print(f"Limiting to first {LIMIT} products (set LIMIT=0 for no limit)")
        total = len(product_urls)
        print(f"Product URLs found: {total}")
        if not total:
            print("No product URLs found. Check category pages and selectors.")
            sys.exit(1)

        success = 0
        failed = 0
        failed_urls: list[str] = []

        with open(products_file, "w", encoding="utf-8") as fout:
            for i, url in enumerate(product_urls, 1):
                print(f"[{i}/{total}] {url[:80]}...")
                try:
                    r = get(url, client=client)
                    r.raise_for_status()
                    parsed = parse_product_page(r.text, url)
                    if not parsed:
                        failed += 1
                        failed_urls.append(url)
                        continue
                    # Append one JSON object per line (JSONL)
                    fout.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                    if upsert_product(parsed):
                        success += 1
                    # If Supabase is configured and upsert failed, we still count as parsed (saved to JSON)
                except Exception as e:
                    print(f"  Error: {e}")
                    failed += 1
                    failed_urls.append(url)

        if failed_urls:
            with open(failed_urls_file, "w", encoding="utf-8") as f:
                f.write("\n".join(failed_urls))
            print(f"\nFailed URLs written to {failed_urls_file}")

    parsed_count = total - failed
    print(f"\nDone. Products parsed: {parsed_count}, Supabase upserted: {success}, failed: {failed}")
    print(f"JSONL: {products_file}")
    if parsed_count > 0 and success == 0 and not DRY_RUN:
        print("NOTE: Nothing was written to Supabase. Add SUPABASE_URL and SUPABASE_KEY to your environment (or GitHub Actions secrets).")


if __name__ == "__main__":
    main()
