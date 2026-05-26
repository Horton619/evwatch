import type { DealTags } from '@evwatch/shared'

/* Lifted from apps/web/lib/format.ts; identical semantics so the desktop
   and web visual languages stay aligned (VEP global guideline). */

export function formatPrice(price: number | null | undefined): string {
  if (price == null) return '—'
  return `$${price.toLocaleString('en-US')}`
}

export function formatMileage(m: number | null | undefined): string {
  if (m == null) return '—'
  return `${m.toLocaleString('en-US')} mi`
}

export function formatDistance(d: number | null | undefined): string {
  if (d == null) return '—'
  return `${d} mi away`
}

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const diffSec = (t - Date.now()) / 1000
  const absSec = Math.abs(diffSec)
  if (absSec < 60) return rtf.format(Math.round(diffSec), 'second')
  if (absSec < 3600) return rtf.format(Math.round(diffSec / 60), 'minute')
  if (absSec < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour')
  if (absSec < 86400 * 30) return rtf.format(Math.round(diffSec / 86400), 'day')
  if (absSec < 86400 * 365)
    return rtf.format(Math.round(diffSec / (86400 * 30)), 'month')
  return rtf.format(Math.round(diffSec / (86400 * 365)), 'year')
}

export function formatYearMakeModel(
  year: number | null,
  make: string | null,
  model: string | null,
  trim?: string | null,
): string {
  const parts: string[] = []
  if (year) parts.push(String(year))
  if (make) parts.push(make)
  if (model) parts.push(model)
  if (trim) parts.push(trim)
  return parts.join(' ') || 'Unknown vehicle'
}

export interface DealBadge {
  label: string
  detail: string
  color: string
}

export function dealBadges(tags: DealTags | null | undefined): DealBadge[] {
  if (!tags) return []
  const out: DealBadge[] = []
  if (tags.BELOW_MARKET) {
    const b = tags.BELOW_MARKET
    const pct = Math.round(b.pct_below * 1000) / 10
    out.push({
      label: 'Below market',
      detail: `${pct}% under $${b.baseline_median.toLocaleString('en-US')} (${b.comp_count} comps)`,
      color: 'bg-emerald-900/40 text-emerald-200 border-emerald-700/40',
    })
  }
  if (tags.PRICE_DROP) {
    const d = tags.PRICE_DROP
    const pct = Math.round(d.delta_pct * 1000) / 10
    out.push({
      label: 'Price drop',
      detail: `$${Math.abs(d.delta).toLocaleString('en-US')} (${pct}%) from $${d.previous_price.toLocaleString('en-US')}`,
      color: 'bg-cyan-900/40 text-cyan-200 border-cyan-700/40',
    })
  }
  if (tags.NEW_PRIORITY) {
    out.push({
      label: 'Priority',
      detail: 'Matches priority watchlist',
      color: 'bg-orange-900/40 text-orange-200 border-orange-700/40',
    })
  }
  return out
}

export function sourceBadge(source: string): { label: string; color: string } {
  switch (source) {
    case 'ebay':
      return { label: 'eBay', color: 'bg-blue-900/40 text-blue-200' }
    case 'carmax':
      return { label: 'CarMax', color: 'bg-amber-900/40 text-amber-200' }
    case 'carvana':
      return { label: 'Carvana', color: 'bg-emerald-900/40 text-emerald-200' }
    case 'craigslist':
      return { label: 'Craigslist', color: 'bg-purple-900/40 text-purple-200' }
    case 'autotempest':
      return { label: 'AutoTempest', color: 'bg-rose-900/40 text-rose-200' }
    case 'cargurus':
      return { label: 'CarGurus', color: 'bg-fuchsia-900/40 text-fuchsia-200' }
    case 'autotrader':
      return { label: 'AutoTrader', color: 'bg-indigo-900/40 text-indigo-200' }
    case 'cars_dot_com':
      return { label: 'Cars.com', color: 'bg-pink-900/40 text-pink-200' }
    default:
      return { label: source, color: 'bg-neutral-800 text-neutral-300' }
  }
}

export function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond > 1_000_000) {
    return `${(bytesPerSecond / 1_000_000).toFixed(1)} MB/s`
  }
  return `${Math.round(bytesPerSecond / 1000)} KB/s`
}

export function formatETA(secondsRemaining: number): string {
  if (secondsRemaining < 60) return `~${Math.round(secondsRemaining)}s left`
  const m = Math.floor(secondsRemaining / 60)
  const s = Math.round(secondsRemaining % 60)
  return `~${m}m ${s}s left`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${(bytes / 1_000).toFixed(0)} KB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}
