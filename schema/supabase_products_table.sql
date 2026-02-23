-- Run this in Supabase SQL Editor. This scraper uses source='miumiu'.
-- For NEW tables (full schema):
-- create table public.products (id text primary key, source text not null default 'miumiu', product_code text not null, product_url text, ...);
--
-- For EXISTING tables, add source if missing:
-- alter table public.products add column if not exists source text default 'miumiu';
-- alter table public.products add column if not exists product_url text;
-- create index if not exists idx_products_source on public.products (source);

create table if not exists public.products (
  id text primary key,
  source text not null default 'miumiu',
  product_code text not null,
  product_url text,
  title text,
  description text,
  price numeric,
  sale_price numeric,
  currency text default 'USD',
  main_image text,
  additional_images jsonb default '[]',
  url text,
  category text,
  categories jsonb default '[]',
  attributes jsonb default '{}',
  raw_data jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists idx_products_source_product_code on public.products (source, product_code);
create index if not exists idx_products_product_code on public.products (product_code);
create index if not exists idx_products_source on public.products (source);
create index if not exists idx_products_category on public.products (category);
create index if not exists idx_products_updated_at on public.products (updated_at);

-- Optional: RLS (enable if you use anon key and want row-level security)
-- alter table public.products enable row level security;
-- create policy "Allow read" on public.products for select using (true);
-- create policy "Allow insert/update by service" on public.products for all using (true);
