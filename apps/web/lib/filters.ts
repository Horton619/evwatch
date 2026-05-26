import "server-only";

import type { Listing } from "@evwatch/shared";
import { getSupabase } from "./supabase";
import { getWatchlist } from "./watchlist";

export const PAGE_SIZE = 50;

export type Quick = "today" | "priority" | null;

export type Sort =
  | "last_seen_desc"
  | "price_asc"
  | "price_desc"
  | "mileage_asc"
  | "year_desc";

export interface Filters {
  make: string | null;
  model: string | null;
  maxPrice: number | null;
  maxMileage: number | null;
  maxDistance: number | null;
  source: string | null;
  quick: Quick;
  sort: Sort;
  page: number;
}

/* ------------------------------------------------------------------ */
/*  URL param parsing                                                  */
/* ------------------------------------------------------------------ */

const VALID_SORTS: Sort[] = [
  "last_seen_desc",
  "price_asc",
  "price_desc",
  "mileage_asc",
  "year_desc",
];

const VALID_QUICKS: Quick[] = ["today", "priority"];

function asString(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v && v.length ? v : null;
}

function asInt(v: string | string[] | undefined): number | null {
  const s = asString(v);
  if (s == null) return null;
  const n = parseInt(s, 10);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function parseFilters(
  searchParams: Record<string, string | string[] | undefined>,
): Filters {
  const sortRaw = asString(searchParams.sort);
  const sort: Sort = VALID_SORTS.includes(sortRaw as Sort)
    ? (sortRaw as Sort)
    : "last_seen_desc";

  const quickRaw = asString(searchParams.quick);
  const quick: Quick = VALID_QUICKS.includes(quickRaw as Quick)
    ? (quickRaw as Quick)
    : null;

  const page = Math.max(1, asInt(searchParams.page) ?? 1);

  return {
    make: asString(searchParams.make),
    model: asString(searchParams.model),
    maxPrice: asInt(searchParams.maxPrice),
    maxMileage: asInt(searchParams.maxMileage),
    maxDistance: asInt(searchParams.maxDistance),
    source: asString(searchParams.source),
    quick,
    sort,
    page,
  };
}

/**
 * Re-encode filters as URL query string. Drops null/default values so the
 * URL stays clean for shareability. Pass `overrides` to flip individual
 * params (e.g. when generating sort-header links).
 */
export function toQuery(f: Partial<Filters>, overrides: Partial<Filters> = {}): string {
  const merged = { ...f, ...overrides } as Partial<Filters>;
  const params = new URLSearchParams();
  if (merged.make) params.set("make", merged.make);
  if (merged.model) params.set("model", merged.model);
  if (merged.maxPrice != null) params.set("maxPrice", String(merged.maxPrice));
  if (merged.maxMileage != null) params.set("maxMileage", String(merged.maxMileage));
  if (merged.maxDistance != null) params.set("maxDistance", String(merged.maxDistance));
  if (merged.source) params.set("source", merged.source);
  if (merged.quick) params.set("quick", merged.quick);
  if (merged.sort && merged.sort !== "last_seen_desc") params.set("sort", merged.sort);
  if (merged.page && merged.page !== 1) params.set("page", String(merged.page));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function hasAnyFilter(f: Filters): boolean {
  return Boolean(
    f.make ||
      f.model ||
      f.maxPrice != null ||
      f.maxMileage != null ||
      f.maxDistance != null ||
      f.source ||
      f.quick,
  );
}

/* ------------------------------------------------------------------ */
/*  Supabase query                                                     */
/* ------------------------------------------------------------------ */

const SORT_COLUMN: Record<Sort, { col: string; asc: boolean }> = {
  last_seen_desc: { col: "last_seen_at", asc: false },
  price_asc:      { col: "price",        asc: true  },
  price_desc:     { col: "price",        asc: false },
  mileage_asc:    { col: "mileage",      asc: true  },
  year_desc:      { col: "year",         asc: false },
};

export interface ListingsResult {
  rows: Listing[];
  total: number;
}

/**
 * Run the listings query against Supabase with the parsed filters applied.
 *
 * Null-distance handling: when maxDistance is set, we want to keep listings
 * whose distance is unknown (per SPEC choice). PostgREST's `lte` is
 * null-rejecting, so we use `.or('miles_from_port_orchard.lte.X,miles_from_port_orchard.is.null')`.
 */
export async function queryListings(f: Filters): Promise<ListingsResult> {
  const sb = getSupabase();
  const sort = SORT_COLUMN[f.sort];
  const offset = (f.page - 1) * PAGE_SIZE;

  let q = sb
    .from("listings")
    .select("*", { count: "exact" })
    .order(sort.col, { ascending: sort.asc, nullsFirst: false })
    .range(offset, offset + PAGE_SIZE - 1);

  if (f.make) q = q.ilike("make", f.make);
  if (f.model) q = q.ilike("model", f.model);
  if (f.source) q = q.eq("source", f.source);
  if (f.maxPrice != null) q = q.lte("price", f.maxPrice);
  if (f.maxMileage != null) q = q.lte("mileage", f.maxMileage);
  if (f.maxDistance != null) {
    q = q.or(
      `miles_from_port_orchard.lte.${f.maxDistance},miles_from_port_orchard.is.null`,
    );
  }

  if (f.quick === "today") {
    const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    q = q.gte("first_seen_at", cutoff);
  }

  if (f.quick === "priority") {
    // Build a PostgREST .or() that ORs together a (make.ilike.X,model.ilike.Y)
    // group per priority entry. Year filtering is applied client-side after
    // fetch since per-entry year ranges differ.
    const wl = getWatchlist();
    const groups = wl.priority_models.map(
      (e) =>
        `and(make.ilike.${e.make},model.ilike.${e.model})`,
    );
    if (groups.length > 0) {
      q = q.or(groups.join(","));
    } else {
      // No priority models configured — return empty.
      q = q.eq("source", "__none__");
    }
  }

  const { data, count, error } = await q;
  if (error) {
    throw new Error(`Supabase query failed: ${error.message}`);
  }

  let rows = (data as Listing[]) ?? [];

  // Apply per-entry year ranges for the priority filter.
  if (f.quick === "priority") {
    const wl = getWatchlist();
    rows = rows.filter((r) => {
      for (const e of wl.priority_models) {
        if (e.make.toLowerCase() !== (r.make ?? "").toLowerCase()) continue;
        if (e.model.toLowerCase() !== (r.model ?? "").toLowerCase()) continue;
        if (!e.years || r.year == null) return true;
        const [lo, hi] = e.years;
        if (r.year >= lo && r.year <= hi) return true;
      }
      return false;
    });
  }

  return { rows, total: count ?? 0 };
}

/**
 * Latest source_runs grouped by source. Reads the last 50 rows and groups
 * in JS — fine for v1 traffic. SPEC §5.6 health page material.
 */
export async function querySourceHealth(): Promise<
  Array<{ source: string; ran_at: string; listings_found: number | null; error: string | null }>
> {
  const sb = getSupabase();
  const { data, error } = await sb
    .from("source_runs")
    .select("source, ran_at, listings_found, error")
    .order("ran_at", { ascending: false })
    .limit(50);
  if (error) throw new Error(`source_runs query failed: ${error.message}`);

  const latest = new Map<
    string,
    { source: string; ran_at: string; listings_found: number | null; error: string | null }
  >();
  for (const row of data ?? []) {
    if (!latest.has(row.source)) latest.set(row.source, row);
  }
  return Array.from(latest.values()).sort((a, b) => a.source.localeCompare(b.source));
}
