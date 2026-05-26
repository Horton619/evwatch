// Row types mirroring the Supabase `evwatch` schema (SPEC §5.3 + migration
// 002). Field naming follows PostgREST output (snake_case) so these can be
// consumed directly from supabase-js responses without remapping.

export type SourceKind = 'live' | 'wayback' | 'manual';

// Per-tag payload shapes written by pipeline.detect_deals (Phase 5).
// Persisted on `evwatch.listings.deal_tags jsonb`. The dashboard reads them
// directly — no recompute on render.
export interface BelowMarketTag {
  pct_below: number;           // 0..1 (e.g. 0.164 = 16.4% below)
  dollars_below: number;       // absolute delta
  baseline_median: number;     // for context in the UI
  comp_count: number;          // baseline confidence indicator
}

export interface PriceDropTag {
  previous_price: number;
  delta: number;               // negative; latest - previous
  delta_pct: number;           // negative; e.g. -0.043 = -4.3%
  observed_at_previous: string;
}

export interface DealTags {
  NEW_PRIORITY?: Record<string, never>;  // intentionally empty payload
  BELOW_MARKET?: BelowMarketTag;
  PRICE_DROP?: PriceDropTag;
  // RECURRENT_LISTING reserved — not yet emitted.
}

export interface Listing {
  id: string;
  source: string;
  source_listing_id: string;
  url: string;
  make: string | null;
  model: string | null;
  trim: string | null;
  year: number | null;
  mileage: number | null;
  price: number | null;
  vin: string | null;
  location: string | null;
  miles_from_port_orchard: number | null;
  thumbnail_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
  removed_at: string | null;
  raw: Record<string, unknown> | null;
  deal_tags: DealTags | null;
}

export interface PriceObservation {
  listing_id: string;
  observed_at: string;
  price: number;
  source_kind: SourceKind;
}

export interface Baseline {
  model_key: string;
  median_price: number | null;
  comp_count: number | null;
  computed_at: string | null;
}

export interface TrendWeekly {
  week_starting: string;
  model_key: string;
  median_price: number | null;
  listing_count: number | null;
  median_days_on_market: number | null;
}

export interface SourceRun {
  id: number;
  source: string;
  ran_at: string;
  duration_ms: number | null;
  listings_found: number | null;
  error: string | null;
}

export interface Digest {
  id: string;
  sent_at: string;
  priority_count: number | null;
  drop_count: number | null;
  deal_count: number | null;
  email_html: string | null;
}
