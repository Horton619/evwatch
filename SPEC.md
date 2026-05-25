# evwatch — Used EV Market Monitor

**Owner:** David Stahl (Visual Entropy Productions)
**Repo:** `evwatch` (public, GitHub)
**Status:** Canonical spec — feed to Claude Code via `SPEC.md` in repo root

---

## 1. Product summary

A pipeline that scrapes used EV listings from multiple sources, detects deals (new matches, price drops, below-market pricing), publishes a web dashboard, sends HTML email digests, and exposes everything through a Mac desktop app for at-home use.

Built around the hypothesis that 2023 off-lease EVs will flood the used market through late 2025–2026. Goal is market visibility + deal alerts, not active shopping.

## 2. User & use case

- **User:** David, based in Port Orchard, WA.
- **Geographic radius:** 100 mi from Port Orchard.
- **Mode:** passive monitoring. Reads digest on phone (Vercel dashboard link), uses Mac app when at desk for richer browsing and to trigger ad-hoc residential-IP scrapes.
- **Action on a deal:** read alert, click through to original listing. No buy/save/contact-seller automation.

## 3. Scope

**In scope (v1):**
- Daily GHA scrape of friendly sources (eBay, CarMax, Carvana, Craigslist, AutoTempest)
- On-demand Mac scrape of anti-bot sources (CarGurus, AutoTrader, Cars.com) via Electron app
- Historical baseline seeding from iSeeCars aggregates + Wayback Machine for priority models
- Deal detection: NEW (priority watchlist), PRICE_DROP, BELOW_MARKET
- HTML email digest via Resend (reusing existing Flux/Calltime config)
- Vercel-hosted web dashboard, public, dynamic, mobile-responsive
- Mac Electron app: live data view + scrape trigger, auto-updating from GitHub Releases
- Supabase Postgres for all state
- Watchlist managed via YAML file edited through Claude Code

**Out of scope (v1):**
- Facebook Marketplace (login required, breaks weekly)
- BaT / Cars & Bids (auction model, different product)
- Snooze, multi-recipient, GUI watchlist editor → deferred to v2
- iOS/Android app — phone access via responsive web dashboard only
- Any kind of buy/bid/contact-seller flow

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│           Flux Supabase project  →  `evwatch` schema                  │
│  listings | price_history | baselines | digests | source_health      │
│           (exposed via PostgREST + RLS, read-anon / write-service)    │
└──────────────────────────────────────────────────────────────────────┘
     ▲              ▲                ▲                ▲          ▲
     │              │                │                │          │
┌────┴───────┐  ┌──┴────────────┐  ┌┴─────────────┐ ┌┴──────────┐│
│ GHA cron   │  │ Mac Electron  │  │ GHA pipeline │ │ Vercel    ││
│ 7am PT     │  │ app           │  │ (post-scrape │ │ Next.js   ││
│            │  │               │  │  every run)  │ │ dashboard ││
│ • eBay     │  │ • CarGurus    │  │              │ │           ││
│ • CarMax   │  │ • AutoTrader  │  │ • detect     │ │ • listings││
│ • Carvana  │  │ • Cars.com    │  │ • baseline   │ │   table   ││
│ • CL RSS   │  │ • live view   │  │ • trends     │ │ • detail  ││
│ • AutoTmpst│  │ • scrape btn  │  │ • email      │ │ • trends  ││
└────────────┘  └───────────────┘  └──────────────┘ └───────────┘│
                                          │                       │
                                          ▼                       │
                                   ┌──────────────┐               │
                                   │ Resend       │◄──────────────┘
                                   │ (existing)   │  reads same data
                                   └──────────────┘
```

**Core idea:** Supabase is the single source of truth. Everything reads/writes there. Email, web dashboard, and desktop app are all just views over the same Postgres.

## 5. Components

### 5.1 Scrapers

Each scraper exposes `scrape(filters) -> list[Listing]` and writes via Supabase client. Stateless — repeat-safe by upsert on stable `(source, source_listing_id)`.

**Friendly sources (run from GHA, also runnable from Mac app):**

| Source | Method | Notes |
|---|---|---|
| eBay Motors | Browse API | Free 5000 calls/day, plenty |
| CarMax | Internal JSON `/cars/api/search` | No auth, stable |
| Carvana | Internal JSON `/cars/search` | No auth |
| Craigslist | RSS per region (Seattle, Tacoma, Olympia, Portland, Bellingham) | Stable, low-fi |
| AutoTempest | HTML scrape | Aggregator — less detail per listing, broad coverage |
| iSeeCars (baseline seed only) | One-time + monthly refresh | Used for market aggregates, not per-listing |

**Anti-bot protected (run from Mac app only):**

| Source | Method | Notes |
|---|---|---|
| CarGurus | Playwright headless Chromium | Capture their deal-rating label too — useful signal |
| AutoTrader | Playwright | OEM-direct programs sometimes here |
| Cars.com | Playwright (try plain requests first) | Less aggressive than CarGurus |

**Historical seeding (one-time, run from Mac):**

| Source | Method | Notes |
|---|---|---|
| Wayback Machine | CDX API + page fetch | Pull 12mo of search-page snapshots for priority models, extract observable prices, write to `price_history` with `source = 'wayback'` flag |
| iSeeCars trends | HTML scrape of model pages | National + regional EV depreciation curves |

### 5.2 Pipeline (`/pipeline/`, run from GHA after each scrape)

Order:

1. **`detect_deals.py`** — tags every listing in the run with zero or more of: `NEW_PRIORITY`, `PRICE_DROP`, `BELOW_MARKET`, `RECURRENT_LISTING`.
2. **`update_baselines.py`** — recomputes per-`(model, year_bucket, mileage_bucket, region)` median prices using last 60 days of observations from both live and Wayback-seeded data.
3. **`build_trends.py`** — weekly aggregate stats per make/model: median price, listing count, days-on-market. Powers the trends view.
4. **`send_digest.py`** — composes HTML email if there are any tagged items. Skips if nothing to report. POSTs to Resend.
5. **`record_run.py`** — writes a `digest_runs` row with what was sent and source health.

### 5.3 Supabase schema (sketch)

All tables live in a dedicated `evwatch` schema inside the existing **Flux** Supabase project. This isolates evwatch data from Flux's `public` schema while sharing the 500 MB database quota (listings are small — projected <50 MB even with years of history).

```sql
-- Run as a migration in the Flux project
create schema if not exists evwatch;

-- Every listing ever observed
create table evwatch.listings (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  source_listing_id text not null,
  url text not null,
  make text, model text, trim text,
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

-- Every price observation (current sources + Wayback historical)
create table evwatch.price_history (
  listing_id uuid references evwatch.listings(id),
  observed_at timestamptz not null,
  price int not null,
  source_kind text not null check (source_kind in ('live', 'wayback', 'manual')),
  primary key (listing_id, observed_at)
);

-- Computed baselines, refreshed daily
create table evwatch.baselines (
  model_key text,           -- e.g. 'tesla:model-y:2022:30k-50k:pnw'
  median_price int,
  comp_count int,
  computed_at timestamptz,
  primary key (model_key)
);

-- Weekly aggregate trends
create table evwatch.trends_weekly (
  week_starting date,
  model_key text,
  median_price int,
  listing_count int,
  median_days_on_market int,
  primary key (week_starting, model_key)
);

-- Source health
create table evwatch.source_runs (
  id bigserial primary key,
  source text not null,
  ran_at timestamptz not null default now(),
  duration_ms int,
  listings_found int,
  error text
);

-- Digest log
create table evwatch.digests (
  id uuid primary key default gen_random_uuid(),
  sent_at timestamptz not null default now(),
  priority_count int, drop_count int, deal_count int,
  email_html text
);

-- RLS: enable on all evwatch tables, read-only for anon, full for service_role
alter table evwatch.listings enable row level security;
create policy "anon read listings" on evwatch.listings for select using (true);
-- (repeat for each table; service_role bypasses RLS by default)
```

**Supabase dashboard step:** in Project Settings → API → Exposed Schemas, add `evwatch` to the list (default is just `public`). This makes the schema queryable via PostgREST so the Vercel dashboard and Electron app can use the anon key.

### 5.4 Watchlist config (`/config/watchlist.yml`)

```yaml
priority_models:
  # 3-row EVs (rare, alert on any new listing)
  - { make: Tesla,  model: "Model X", years: [2018, 2024] }
  - { make: Kia,    model: "EV9",     years: [2024, 2026] }
  - { make: Rivian, model: "R1S",     years: [2022, 2026] }
  - { make: Volvo,  model: "EX90",    years: [2024, 2026] }
  - { make: Lucid,  model: "Gravity", years: [2024, 2026] }

broad_models:
  # Large 5-seat — alert only if BELOW_MARKET or PRICE_DROP
  - { make: Tesla,    model: "Model Y" }
  - { make: Ford,     model: "Mustang Mach-E" }
  - { make: Hyundai,  model: "Ioniq 5" }
  - { make: Kia,      model: "EV6" }
  - { make: Nissan,   model: "Ariya" }
  - { make: Cadillac, model: "Lyriq" }
  - { make: VW,       model: "ID.4" }
  - { make: Ford,     model: "F-150 Lightning" }
  - { make: Rivian,   model: "R1T" }
  - { make: Chevrolet, model: "Silverado EV" }

filters:
  origin_zip: "98366"
  radius_miles: 100
  max_mileage: 80000
  min_year: 2020
  exclude_salvage: true
  exclude_rebuilt: true

thresholds:
  deal_pct_below_baseline: 0.15
  price_drop_min_dollars: 500
  price_drop_min_pct: 0.03
  min_baseline_comps: 6           # was 8 in v1, lowered for 1wk firehose
  firehose_days: 7                # all matching listings emailed for first week
```

### 5.5 Email digest

Reuses existing Resend config from Flux/Calltime stack — no new domain verification needed.

Subject patterns:
- Cold-start week: `[evwatch] day 3/7 — 14 new listings`
- Steady state: `[evwatch] 2 priority, 4 deals, 6 drops`
- Quiet: `[evwatch] 1 priority hit`

Sections (only included if non-empty):
1. **Priority watchlist** (3-row models — any new)
2. **Below-market deals**
3. **Price drops**
4. **Weekly trends snapshot** — included on Mondays only
5. **Footer:** dashboard link, source health summary, total listings tracked

Each listing card: thumbnail, year/make/model, current price, prior price (if dropped), $ delta from baseline (if computed), mileage, distance from Port Orchard, source badge, deep link to original listing, deep link to dashboard detail page.

### 5.6 Vercel dashboard (Next.js)

`evwatch.veproductions.net` (or similar). Public, no auth in v1.

**Important:** server-side-rendered only. Next.js 15 app router with server components. The Supabase anon key lives in Vercel server-side env vars and is never shipped to the browser — all queries happen on Vercel's edge runtime, HTML is rendered server-side, client receives only static markup. Filter state lives in URL params (`?make=tesla&maxPrice=35000`), so changing filters is a server roundtrip, not a client-side Supabase call. This keeps the dashboard fully public without exposing any credentials.

Pages:
- **`/`** — sortable, filterable table of current listings. Filters: make, model, year, price range, mileage, source, distance. Quick filters at top for "new today / price drops / deals." Filter state in URL.
- **`/listing/[id]`** — detail page. Photo, full specs, price history sparkline (from `price_history`), CarGurus deal label if known, link to original.
- **`/trends`** — per-model weekly median price chart, listing volume chart. Year-over-year comparison once data exists.
- **`/health`** — internal-ish page showing which scrapers ran when and what they found. Useful for debugging.

Minor client-side JS allowed for: sort-column clicks (could also be SSR via URL params), sparkline rendering (inline SVG, no data fetching), responsive nav menu. No client-side data fetching.

### 5.7 Mac Electron app

**Stack:** Electron + React + TypeScript (matches SlideFluid). Bundled with `electron-builder`, distributed via GitHub Releases, auto-updates via `electron-updater`.

**Window layout:**
- Left sidebar:
  - Source health indicators (green/yellow/red per source)
  - Last successful run timestamps
  - Big "Scrape Now" button (runs all scrapers, friendly + blocked)
  - Smaller "Blocked only" button (just the Playwright scrapers)
  - Filter controls (same as dashboard)
- Main panel:
  - Tabs: **Live**, **Deals**, **Drops**, **Trends**, **Source Log**
  - Each tab is a virtualized list/table backed by Supabase queries
- Top right: connection status, app version, "Update available" indicator

**Scrape execution:**
- App ships Python runtime via `python-shell` or PyInstaller-bundled binaries (matching SlideFluid pattern)
- Click "Scrape Now" → spawns Python subprocess for each scraper, streams logs to a console view
- Scrapers write directly to Supabase (no intermediate file)
- App polls Supabase for new rows during scrape, updates UI live

**Auto-update flow:**
- `electron-updater` checks GitHub Releases on app launch and every 6 hours
- Downloads in background, prompts on quit
- Repo: `evwatch` releases assets `evwatch-mac-x64.dmg` + `evwatch-mac-arm64.dmg`
- Releases built by GHA on tagged commits

**v1 scope explicitly excludes:** GUI watchlist editor, in-app config UI, custom filter persistence. Filters live in `watchlist.yml`, edited via Claude Code.

## 6. Historical baseline strategy

Honest scoping: per-listing historical price data is hard to obtain cleanly. Approach:

1. **Day 1, before any scraping:** scrape iSeeCars EV depreciation pages for our priority + broad models. Store as `baselines` seed rows with `comp_count = -1` (synthetic flag) and a wider error band.
2. **Days 1–7 (firehose):** every matching listing emailed, even if it's not a "deal." This builds visibility while baselines are thin.
3. **Days 1–14, low-priority background job:** Wayback Machine sweep for priority models. CDX API to list snapshots of `cargurus.com/Cars/inventorylisting/...` and similar URLs over last 12 months, fetch, parse, write observations to `price_history` with `source_kind = 'wayback'`. Slow (rate-limited by archive.org), runs from Mac.
4. **Day 7+:** real baselines computed from live data start replacing seeded ones as `comp_count` grows. Mixed source baseline acceptable as long as we mark which is which.
5. **Ongoing:** weekly trend snapshots build up the "2026 vs 2025" comparison data over time. After ~6 months we'll have real YoY signal; before that the comparison is iSeeCars-derived.

**Caveat to call out clearly in the dashboard:** baselines with `comp_count < min_baseline_comps` or `comp_count = -1` are labeled "estimated" or "low confidence" in the UI. Don't fake precision.

## 7. Setup & secrets

**One-time:**
1. Create GitHub repo `evwatch` (public)
2. Add `evwatch` schema to the existing **Flux** Supabase project (single migration file)
3. In Supabase dashboard → Project Settings → API → add `evwatch` to **Exposed Schemas**
4. Reuse Flux's existing `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — copy to evwatch GHA secrets + Vercel env
5. Reuse Resend API key from Flux/Calltime — add to GHA secrets
6. eBay developer App ID + Cert ID (client secret — both needed for the Browse API's OAuth2 client-credentials grant) → GHA secrets
7. Configure Vercel project pointed at the repo (separate from Flux's Vercel deployment)
8. Custom domain (optional): `evwatch.veproductions.net` → Vercel
9. Mac: install Node 20, Python 3.11, Playwright Chromium
10. First build: `pnpm install && pnpm build:electron && open dist/evwatch.dmg`
11. Sign in to Electron app with the shared Flux anon key (baked into build)

**Secrets** (all shared with Flux except evwatch-specific ones):

| Secret | Where | Purpose |
|---|---|---|
| `SUPABASE_URL` | GHA, Vercel (server env), Electron build | Flux project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | GHA only | Write access from scrapers (bypasses RLS) |
| `SUPABASE_ANON_KEY` | Vercel (server env only), Electron build | Read access via RLS policies |
| `RESEND_API_KEY` | GHA only | Email send (shared with Flux) |
| `EBAY_APP_ID` | GHA, Mac | eBay Browse API — OAuth2 client id |
| `EBAY_CERT_ID` | GHA, Mac | eBay Browse API — OAuth2 client secret |
| `EVWATCH_DIGEST_FROM` (GHA var, optional) | GHA | Sender address for the email digest. Defaults to `noreply@veproductions.net`. |
| `EVWATCH_DIGEST_TO` (GHA var, optional) | GHA | Recipient. Defaults to `dave@veproductions.net`. |
| `EVWATCH_DASHBOARD_URL` (GHA var, optional) | GHA | Dashboard URL in email footers. Defaults to `https://evwatch.veproductions.net`. |
| `ARCHIVE_ORG_USER` (optional) | Mac | Higher rate limit on Wayback |

**Note on `SUPABASE_ANON_KEY` in Vercel:** set as a regular server-side env var, *not* `NEXT_PUBLIC_*`. The dashboard's SSR-only design means it never needs to reach the browser.

## 8. Repo structure

```
evwatch/
├── apps/
│   ├── desktop/                  # Electron app
│   │   ├── electron/main.ts
│   │   ├── src/                  # React UI
│   │   └── package.json
│   └── web/                      # Next.js dashboard for Vercel
│       ├── app/
│       └── package.json
├── packages/
│   └── shared/                   # TS types shared between desktop + web
├── scrapers/                     # Python
│   ├── _common.py
│   ├── ebay.py
│   ├── carmax.py
│   ├── carvana.py
│   ├── craigslist.py
│   ├── autotempest.py
│   ├── iseecars.py               # baseline seeder
│   ├── wayback.py                # historical seeder
│   ├── cargurus.py               # Mac-only
│   ├── autotrader.py             # Mac-only
│   └── cars_dot_com.py           # Mac-only
├── pipeline/                     # Python
│   ├── detect_deals.py
│   ├── update_baselines.py
│   ├── build_trends.py
│   ├── send_digest.py
│   └── record_run.py
├── infra/
│   ├── supabase/migrations/
│   └── github/workflows/
│       ├── daily.yml             # 7am PT cron
│       ├── release-desktop.yml   # on tag, builds + releases Mac app
│       └── deploy-web.yml        # on push, Vercel handles
├── config/watchlist.yml
├── templates/email.html.j2
├── pyproject.toml
├── pnpm-workspace.yaml
└── README.md
```

## 9. Build sequence

Suggested order for Claude Code to build:

1. Repo scaffold, Supabase migrations, watchlist.yml, shared TS types
2. `scrapers/_common.py` (Listing dataclass + Supabase upsert helper)
3. One scraper end-to-end (start with eBay — cleanest API)
4. `detect_deals.py` with just `NEW_PRIORITY` logic
5. `send_digest.py` with stub data → verify Resend works
6. GHA workflow wires the above → verify daily run end-to-end
7. Remaining friendly scrapers
8. Vercel dashboard MVP (just the listings table)
9. Baseline computation + `BELOW_MARKET` detection
10. Electron app scaffold with live data view + Scrape Now button (no auto-update yet)
11. Mac-only Playwright scrapers wired to Electron
12. Auto-update via electron-updater + GitHub Releases workflow
13. iSeeCars seeding + Wayback historical sweep (background polish)
14. Trends view (web + Electron)

Each step ends in a working state — don't gate v1 on later steps.

## 10. Open questions

- [ ] **Subdomain:** `evwatch.veproductions.net` OK? Or something else?
- [ ] **Public dashboard:** confirmed in v1, but worth re-noting: anyone with the URL sees the data. Listings themselves are already public, but your *watchlist* (priority models, filters) reveals your shopping interest. Acceptable?
- [ ] **Flux DB headroom:** Flux currently uses ~X MB of the 500 MB free-tier limit (check before launch). evwatch will add ~20–50 MB at steady state. Confirm there's runway.
- [ ] **Electron code signing:** SlideFluid presumably has this figured out — reuse the cert?
- [ ] **iSeeCars TOS:** their pages may be scraping-restricted. If so, swap for Edmunds or Cars.com depreciation pages.
- [ ] **Cold start UX:** during the 7-day firehose, emails might be long. Cap at N listings with "X more on dashboard" overflow?
- [x] ~~**Anon key in Electron app:**~~ Accepted: app is single-Mac, never distributed. Obscurity sufficient. RLS still enforced for defense in depth.

## 11. How to build this with Claude Code

Build phase-by-phase, each phase in its own Claude Code session. Don't try to build everything in one shot — control loss compounds.

**Phase boundaries follow §9 build sequence.** Suggested grouping:

| Phase | Spec §9 steps | Outcome |
|---|---|---|
| 1 | 1 | Scaffolded monorepo, schema migration, watchlist.yml |
| 2 | 2–6 | Working email digest from eBay alone, running daily on GHA |
| 3 | 7 | All friendly scrapers landing data |
| 4 | 8 | Vercel dashboard MVP live |
| 5 | 9 | Baselines + BELOW_MARKET deal detection |
| 6 | 10–12 | Electron app with Scrape Now, auto-update, blocked-site scrapers |
| 7 | 13 | Historical seeding (iSeeCars + Wayback) |
| 8 | 14 | Trends view |

For each phase: paste the corresponding kickoff prompt into a fresh Claude Code session pointed at `~/evwatch`. Each prompt should reference this SPEC.md by section number, define in-scope and out-of-scope explicitly, and require Claude Code to confirm a plan before writing code.
