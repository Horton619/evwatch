import { useEffect, useState } from 'react'
import type { SourceHealthRow } from '../lib/queries'
import { fetchSourceHealth } from '../lib/queries'
import { formatRelativeTime } from '../lib/format'

interface Props {
  scraping: boolean
  scrapeMode: 'all' | 'blocked' | null
  onScrapeNow: (mode: 'all' | 'blocked') => void
  onCancelScrape: () => void
  /** Bumped after a scrape batch completes so the panel re-queries. */
  refreshTick: number
}

const STALE_MS = 36 * 60 * 60 * 1000

export function Sidebar({
  scraping,
  scrapeMode,
  onScrapeNow,
  onCancelScrape,
  refreshTick,
}: Props): React.JSX.Element {
  const [health, setHealth] = useState<SourceHealthRow[]>([])
  const [healthError, setHealthError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchSourceHealth()
      .then((rows) => {
        if (!cancelled) {
          setHealth(rows)
          setHealthError(null)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setHealthError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [refreshTick])

  return (
    <aside className="w-64 shrink-0 border-r border-neutral-900 flex flex-col p-4 gap-5 bg-[#0a0d16]">
      <section>
        <h2 className="text-[10px] tracking-[0.2em] uppercase text-neutral-500 mb-2">
          Source health
        </h2>
        {healthError ? (
          <div className="text-xs text-rose-400">{healthError}</div>
        ) : (
          <ul className="space-y-1">
            {health.length === 0 ? (
              <li className="text-xs text-neutral-600">No runs logged.</li>
            ) : (
              health.map((row) => {
                const t = Date.parse(row.ran_at)
                const stale = Number.isFinite(t) && Date.now() - t > STALE_MS
                const color = row.error
                  ? 'bg-rose-500'
                  : stale
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                return (
                  <li
                    key={row.source}
                    title={
                      row.error
                        ? `Error: ${row.error}`
                        : `${row.listings_found ?? 0} listings, ${formatRelativeTime(row.ran_at)}`
                    }
                    className="flex items-center gap-2 text-xs text-neutral-400"
                  >
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${color}`}
                      aria-hidden
                    />
                    <span className="font-mono flex-1 truncate">{row.source}</span>
                    <span className="text-neutral-600">
                      {formatRelativeTime(row.ran_at)}
                    </span>
                  </li>
                )
              })
            )}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        {scraping ? (
          <>
            <div className="text-xs text-neutral-400 text-center py-2">
              Scraping ({scrapeMode === 'blocked' ? 'blocked sources' : 'all sources'})…
            </div>
            <button
              onClick={onCancelScrape}
              className="w-full py-2 rounded border border-rose-700 text-rose-300 hover:bg-rose-950 transition-colors text-sm"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => onScrapeNow('all')}
              className="w-full py-3 rounded bg-orange-500 hover:bg-orange-400 text-neutral-950 font-semibold transition-colors"
            >
              Scrape Now
            </button>
            <button
              onClick={() => onScrapeNow('blocked')}
              className="w-full py-2 rounded border border-neutral-700 text-neutral-300 hover:border-neutral-500 transition-colors text-sm"
            >
              Blocked sources only
            </button>
          </>
        )}
      </section>

      <div className="mt-auto text-[10px] text-neutral-700 leading-relaxed">
        Sources spawn the local Python venv. Scrapes write directly to
        Supabase; tags refresh on completion.
      </div>
    </aside>
  )
}
