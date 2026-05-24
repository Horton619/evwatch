// Row types mirroring the Supabase `evwatch` schema (SPEC §5.3).
// Field naming follows PostgREST output (snake_case) so these can be
// consumed directly from supabase-js responses without remapping.

export type SourceKind = 'live' | 'wayback' | 'manual';

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
