import { useEffect, useState } from 'react'
import type { Listing } from '@evwatch/shared'
import { ListingsTable } from './ListingsTable'

interface Props {
  fetcher: () => Promise<Listing[]>
  emptyHint?: string
  /** Bumped after scrape completes so the tab re-queries. */
  refreshTick: number
}

export function ListingsTab({
  fetcher,
  emptyHint,
  refreshTick,
}: Props): React.JSX.Element {
  const [rows, setRows] = useState<Listing[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetcher()
      .then((r) => {
        if (!cancelled) {
          setRows(r)
          setError(null)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // Re-run whenever fetcher, refreshTick (from main process) or
    // manual reload changes.
  }, [fetcher, refreshTick, reloadTick])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between py-2">
        <div className="text-xs text-neutral-500">
          {loading ? 'Loading…' : `${rows.length} listings`}
        </div>
        <button
          onClick={() => setReloadTick((t) => t + 1)}
          className="text-xs text-neutral-400 hover:text-neutral-200 px-2 py-1 rounded border border-neutral-800 hover:border-neutral-600"
        >
          Refresh
        </button>
      </div>
      {error ? (
        <div className="border border-rose-900 rounded-lg p-4 text-sm text-rose-300">
          {error}
        </div>
      ) : (
        <div className="flex-1 overflow-hidden">
          <ListingsTable rows={rows} emptyHint={emptyHint} />
        </div>
      )}
    </div>
  )
}
