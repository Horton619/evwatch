import type { Listing } from '@evwatch/shared'
import { getSupabase } from './supabase'

export const PAGE_LIMIT = 500

/** Currently-listed cars (removed_at is null), ordered by recency. */
export async function fetchLiveListings(): Promise<Listing[]> {
  const sb = getSupabase()
  const { data, error } = await sb
    .from('listings')
    .select('*')
    .is('removed_at', null)
    .order('last_seen_at', { ascending: false })
    .limit(PAGE_LIMIT)
  if (error) throw new Error(error.message)
  return (data as Listing[]) ?? []
}

/** Listings tagged BELOW_MARKET, deepest discount first. */
export async function fetchDeals(): Promise<Listing[]> {
  const sb = getSupabase()
  const { data, error } = await sb
    .from('listings')
    .select('*')
    .is('removed_at', null)
    .filter('deal_tags', 'cs', '{"BELOW_MARKET":{}}')
    .order('deal_tags->BELOW_MARKET->>pct_below', { ascending: false, nullsFirst: false })
    .limit(PAGE_LIMIT)
  if (error) throw new Error(error.message)
  return (data as Listing[]) ?? []
}

/** Listings tagged PRICE_DROP, most recent first. */
export async function fetchDrops(): Promise<Listing[]> {
  const sb = getSupabase()
  const { data, error } = await sb
    .from('listings')
    .select('*')
    .is('removed_at', null)
    .filter('deal_tags', 'cs', '{"PRICE_DROP":{}}')
    .order('last_seen_at', { ascending: false })
    .limit(PAGE_LIMIT)
  if (error) throw new Error(error.message)
  return (data as Listing[]) ?? []
}

export interface SourceHealthRow {
  source: string
  ran_at: string
  listings_found: number | null
  error: string | null
}

/** Latest source_runs grouped by source. Reads last 100 rows. */
export async function fetchSourceHealth(): Promise<SourceHealthRow[]> {
  const sb = getSupabase()
  const { data, error } = await sb
    .from('source_runs')
    .select('source, ran_at, listings_found, error')
    .order('ran_at', { ascending: false })
    .limit(100)
  if (error) throw new Error(error.message)
  const latest = new Map<string, SourceHealthRow>()
  for (const row of (data as SourceHealthRow[]) ?? []) {
    if (!latest.has(row.source)) latest.set(row.source, row)
  }
  return Array.from(latest.values()).sort((a, b) =>
    a.source.localeCompare(b.source),
  )
}
