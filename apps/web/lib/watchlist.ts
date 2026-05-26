import "server-only";

import fs from "node:fs";
import path from "node:path";
import { parse } from "yaml";

export interface WatchlistEntry {
  make: string;
  model: string;
  years?: [number, number];
}

export interface Watchlist {
  priority_models: WatchlistEntry[];
  broad_models: WatchlistEntry[];
  filters: {
    origin_zip: string;
    radius_miles: number;
    max_mileage: number;
    min_year: number;
    exclude_salvage: boolean;
    exclude_rebuilt: boolean;
  };
  thresholds: Record<string, number>;
}

let _cached: Watchlist | null = null;

function findWatchlistPath(): string {
  // Candidate paths cover three contexts:
  //  1. `pnpm dev:web` from repo root → cwd = repo root
  //  2. `cd apps/web && pnpm dev`      → cwd = apps/web
  //  3. Vercel production (file traced in via next.config outputFileTracingIncludes)
  //     → cwd = apps/web at runtime in the function
  const cwd = process.cwd();
  const candidates = [
    path.join(cwd, "config/watchlist.yml"),
    path.join(cwd, "../../config/watchlist.yml"),
    path.join(cwd, "../config/watchlist.yml"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error(
    `watchlist.yml not found from cwd=${cwd}. Tried: ${candidates.join(", ")}`,
  );
}

export function getWatchlist(): Watchlist {
  if (_cached) return _cached;
  const p = findWatchlistPath();
  const raw = fs.readFileSync(p, "utf-8");
  _cached = parse(raw) as Watchlist;
  return _cached;
}

/**
 * True iff the given (make, model) is in the priority watchlist AND the
 * year (if present) falls in the configured range.
 */
export function isPriorityMatch(
  make: string | null,
  model: string | null,
  year: number | null,
): boolean {
  if (!make || !model) return false;
  const wl = getWatchlist();
  const mk = make.toLowerCase();
  const md = model.toLowerCase();
  for (const entry of wl.priority_models) {
    if (entry.make.toLowerCase() !== mk) continue;
    if (entry.model.toLowerCase() !== md) continue;
    if (!entry.years || year == null) return true;
    const [lo, hi] = entry.years;
    if (year >= lo && year <= hi) return true;
  }
  return false;
}

/** All distinct makes across priority + broad lists, for the filter dropdown. */
export function allMakes(): string[] {
  const wl = getWatchlist();
  const set = new Set<string>();
  for (const e of [...wl.priority_models, ...wl.broad_models]) set.add(e.make);
  return Array.from(set).sort();
}

/** All distinct (make, model) pairs, for the filter dropdown. */
export function allModels(): { make: string; model: string }[] {
  const wl = getWatchlist();
  const out = [...wl.priority_models, ...wl.broad_models].map((e) => ({
    make: e.make,
    model: e.model,
  }));
  out.sort((a, b) =>
    a.make === b.make ? a.model.localeCompare(b.model) : a.make.localeCompare(b.make),
  );
  return out;
}
