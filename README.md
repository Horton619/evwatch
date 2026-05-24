# evwatch

Used EV market monitor for the Pacific Northwest. Scrapes listings daily,
detects deals (new priority matches, price drops, below-market), emails an
HTML digest, publishes a public web dashboard, and ships a Mac desktop app
for live browsing + on-demand scrapes of anti-bot-protected sources.

See [`SPEC.md`](./SPEC.md) for the full architecture, data model, and build
sequence.

## Status

**Phase 1: scaffold.** Empty monorepo + schema migration + watchlist config.
No scraper or pipeline logic yet. Tracking SPEC §11 phase plan.

## Setup

One-time:

1. **Clone + install JS deps** (pnpm 9 required — `corepack enable` or `npm i -g pnpm@9`):

   ```sh
   pnpm install
   ```

2. **Create a Python venv and install deps:**

   ```sh
   python3 -m venv venv
   venv/bin/pip install -e .
   venv/bin/playwright install chromium
   ```

3. **Add the `evwatch` schema to the existing Flux Supabase project.** Paste
   [`infra/supabase/migrations/001_init.sql`](./infra/supabase/migrations/001_init.sql)
   into the Flux project's SQL editor and run it.

4. **Expose the schema via PostgREST.** In the Supabase dashboard go to
   Project Settings → API → Exposed Schemas and add `evwatch` to the list
   (default is just `public`). Without this the dashboard and desktop app
   can't query the new tables.

5. **Reuse Flux credentials.** Copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `SUPABASE_SERVICE_ROLE_KEY`, and `RESEND_API_KEY` from the existing Flux
   project into this repo's GitHub Actions secrets and Vercel env vars.

6. **eBay Browse API.** Register at https://developer.ebay.com (free tier:
   5000 calls/day) and add `EBAY_APP_ID` to GHA secrets.

7. **Local `.env`.** Copy `.env.example` to `.env` and fill in. Never commit
   `.env`.

8. **Vercel.** Create a new Vercel project pointed at this repo (separate
   from Flux's). Set the four Supabase env vars as **regular** server-side
   env vars — NOT `NEXT_PUBLIC_*`. The dashboard is SSR-only and the anon
   key must never reach the browser.

9. **(Optional) Custom domain** `evwatch.veproductions.net` → Vercel.

10. **First desktop build (when Phase 6 lands):**

    ```sh
    pnpm build:mac
    open apps/desktop/dist/*.dmg
    ```

## Dev commands

```sh
pnpm dev:web         # Next.js dashboard, http://localhost:3000
pnpm dev:desktop     # Electron app with HMR
pnpm typecheck       # all workspaces
pnpm build:web
pnpm build:desktop
```

## Repo layout

```
apps/desktop/        Electron + React + TS (Mac live view + scrape trigger)
apps/web/            Next.js 15 SSR dashboard for Vercel
packages/shared/     TS types shared between desktop + web
scrapers/            Python — one module per source (eBay, CarMax, ...)
pipeline/            Python — detect_deals, baselines, trends, digest, run log
infra/supabase/      SQL migrations
.github/workflows/   GHA cron + release builds
config/watchlist.yml The priority + broad model list, filters, thresholds
templates/           Jinja2 email template
```

## License

MIT — see [`LICENSE`](./LICENSE).
