-- Run this in Supabase SQL Editor to create the products table.
-- Adjust types/lengths if your existing schema differs.

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  product_code text unique not null,
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

create index if not exists idx_products_product_code on public.products (product_code);
create index if not exists idx_products_category on public.products (category);
create index if not exists idx_products_updated_at on public.products (updated_at);

-- Optional: RLS (enable if you use anon key and want row-level security)
-- alter table public.products enable row level security;
-- create policy "Allow read" on public.products for select using (true);
-- create policy "Allow insert/update by service" on public.products for all using (true);
