-- evwatch initial schema.
-- Runs as a migration inside the existing Flux Supabase project.
-- After applying, add `evwatch` to Project Settings -> API -> Exposed Schemas
-- so PostgREST will surface it for the Vercel dashboard and Electron app
-- using the anon key.

create schema if not exists evwatch;

-- Every listing ever observed across all sources.
create table evwatch.listings (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  source_listing_id text not null,
  url text not null,
  make text,
  model text,
  trim text,
  year int,
  mileage int,
  price int,
  vin text,
  location text,
  miles_from_port_orchard int,
  thumbnail_url text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  removed_at timestamptz,
  raw jsonb,
  unique (source, source_listing_id)
);

-- Every price observation (current sources + Wayback historical).
create table evwatch.price_history (
  listing_id uuid references evwatch.listings(id),
  observed_at timestamptz not null,
  price int not null,
  source_kind text not null check (source_kind in ('live', 'wayback', 'manual')),
  primary key (listing_id, observed_at)
);

-- Computed baselines, refreshed daily.
create table evwatch.baselines (
  model_key text,           -- e.g. 'tesla:model-y:2022:30k-50k:pnw'
  median_price int,
  comp_count int,
  computed_at timestamptz,
  primary key (model_key)
);

-- Weekly aggregate trends.
create table evwatch.trends_weekly (
  week_starting date,
  model_key text,
  median_price int,
  listing_count int,
  median_days_on_market int,
  primary key (week_starting, model_key)
);

-- Source health log — one row per scraper invocation.
create table evwatch.source_runs (
  id bigserial primary key,
  source text not null,
  ran_at timestamptz not null default now(),
  duration_ms int,
  listings_found int,
  error text
);

-- Digest log — one row per email digest sent.
create table evwatch.digests (
  id uuid primary key default gen_random_uuid(),
  sent_at timestamptz not null default now(),
  priority_count int,
  drop_count int,
  deal_count int,
  email_html text
);

-- RLS: enable on every table. Anon gets read-only via explicit policies;
-- writes happen exclusively from GHA / the desktop app using service_role,
-- which bypasses RLS.

alter table evwatch.listings       enable row level security;
alter table evwatch.price_history  enable row level security;
alter table evwatch.baselines      enable row level security;
alter table evwatch.trends_weekly  enable row level security;
alter table evwatch.source_runs    enable row level security;
alter table evwatch.digests        enable row level security;

create policy "anon read listings"      on evwatch.listings      for select using (true);
create policy "anon read price_history" on evwatch.price_history for select using (true);
create policy "anon read baselines"     on evwatch.baselines     for select using (true);
create policy "anon read trends_weekly" on evwatch.trends_weekly for select using (true);
create policy "anon read source_runs"   on evwatch.source_runs   for select using (true);
create policy "anon read digests"       on evwatch.digests       for select using (true);
