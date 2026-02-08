# Miu Miu Scraper

Scrapes the full Miu Miu catalog and syncs to Supabase: **title**, **description**, **prices**, **main image**, **additional images**, category, attributes, and all other available fields.

## Setup

1. **Python 3.10+**

2. **Install dependencies**
   ```bash
   cd c:\Scrapers\scraper-miumiu
   pip install -r requirements.txt
   ```

3. **Supabase**
   - Create your table in the Supabase SQL Editor using `schema/supabase_products_table.sql` (or align the scraper to your existing table).
   - Copy `.env.example` to `.env` and set:
     - `SUPABASE_URL` — project URL
     - `SUPABASE_KEY` — service role or anon key

4. **Optional env**
   - `BASE_URL` — default `https://www.miumiu.com`
   - `MARKET` / `COUNTRY` — e.g. `en`, `us` (site path `/us/en/...`)
   - `DRY_RUN=1` — only write `output/products.jsonl`, no Supabase upload

## Run

From the project root:

```bash
python main.py
```

- Uses **EU** site by default (`COUNTRY=eu`) because the EU pages embed full product JSON; the US site loads it via JS.
- Discovers product URLs from category pages (including **pagination** `/page/2`, `/page/3`, … and `/c/CODE` listing URLs) so the full catalog is scraped, not just the first page per category.
- Fetches each product page, parses embedded JSON for:
  - **title**, **description**, **short_description**
  - **price**, **sale_price**, **currency**, **formatted_price**
  - **main_image**, **additional_images**
  - **category**, **categories** (breadcrumb)
  - **attributes** (color, material, size, etc.)
  - **product_code**, **url**, **raw_data** (full API blob)
- Appends each product to `output/products.jsonl` (one JSON object per line).
- Upserts into Supabase `products` table (by `product_code`).

Outputs:
- `output/products.jsonl` — all scraped products (JSONL).
- `output/failed_urls.txt` — URLs that failed to parse or fetch (if any).

## Automation (GitHub Actions)

The scraper runs **every day at midnight UTC** and can be **run manually** anytime:

1. In your repo go to **Settings → Secrets and variables → Actions** and add:
   - `SUPABASE_URL` — your Supabase project URL  
   - `SUPABASE_KEY` — your Supabase service role or anon key  
   Without these, the workflow runs but **nothing is written to your database** (you’ll see “Supabase upserted: 0” and a note in the log).

2. **Manual run:** **Actions** → **Run scraper** → **Run workflow** (button on the right).

3. **Schedule:** The workflow runs at `0 0 * * *` (00:00 UTC). To change the time, edit `.github/workflows/scrape.yml` and the `cron` expression (e.g. `0 6 * * *` for 06:00 UTC).

4. After each run, `output/` is uploaded as an artifact (kept 7 days) so you can download `products.jsonl` and `failed_urls.txt` from the run page.

## If your Supabase table differs

Edit `scraper/supabase_client.py` → `_row_for_supabase()` to map our fields to your column names. The full parsed object (including `raw_data`) is always in the JSONL file.
