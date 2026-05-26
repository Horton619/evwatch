import { useEffect, useState } from 'react'
import { getSupabase } from '../lib/supabase'
import { formatRelativeTime, sourceBadge } from '../lib/format'

interface SourceRun {
  id: number
  source: string
  ran_at: string
  duration_ms: number | null
  listings_found: number | null
  error: string | null
}

interface Props {
  refreshTick: number
}

export function SourceLogTab({ refreshTick }: Props): React.JSX.Element {
  const [rows, setRows] = useState<SourceRun[]>([])
  const [error, setError] = useState<string | null>(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    getSupabase()
      .from('source_runs')
      .select('id, source, ran_at, duration_ms, listings_found, error')
      .order('ran_at', { ascending: false })
      .limit(200)
      .then(({ data, error: err }) => {
        if (cancelled) return
        if (err) setError(err.message)
        else {
          setRows((data ?? []) as SourceRun[])
          setError(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [refreshTick, reloadTick])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between py-2">
        <div className="text-xs text-neutral-500">
          {rows.length} runs (last 200)
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
        <div className="overflow-auto flex-1">
          <table className="w-full text-xs selectable">
            <thead>
              <tr className="text-left text-[10px] tracking-[0.2em] uppercase text-neutral-500 border-b border-neutral-800 sticky top-0 bg-[#070910] z-[1]">
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Duration</th>
                <th className="py-2 pr-3 font-medium">Listings</th>
                <th className="py-2 pr-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const badge = sourceBadge(r.source)
                return (
                  <tr
                    key={r.id}
                    className="border-b border-neutral-900 hover:bg-neutral-900/40"
                  >
                    <td className="py-1.5 pr-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-[10px] font-medium ${badge.color}`}
                      >
                        {badge.label}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-neutral-400 tabular-nums">
                      {formatRelativeTime(r.ran_at)}
                    </td>
                    <td className="py-1.5 pr-3 text-neutral-500 tabular-nums">
                      {r.duration_ms != null
                        ? `${(r.duration_ms / 1000).toFixed(1)}s`
                        : '—'}
                    </td>
                    <td className="py-1.5 pr-3 text-neutral-300 tabular-nums">
                      {r.listings_found ?? 0}
                    </td>
                    <td className="py-1.5 pr-3">
                      {r.error ? (
                        <span
                          className="text-rose-300 text-[11px]"
                          title={r.error}
                        >
                          ✕ {r.error.slice(0, 60)}
                        </span>
                      ) : (
                        <span className="text-emerald-400 text-[11px]">ok</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
