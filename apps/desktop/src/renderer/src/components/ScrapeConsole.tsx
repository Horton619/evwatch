import { useEffect, useRef } from 'react'
import type { ScrapeLogEvent, ScrapeStatusEvent } from '../../../preload/index'
import { sourceBadge } from '../lib/format'

interface Props {
  logs: ScrapeLogEvent[]
  statuses: Map<string, ScrapeStatusEvent>
}

export function ScrapeConsole({ logs, statuses }: Props): React.JSX.Element {
  const consoleRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new logs.
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [logs.length])

  return (
    <div className="border border-neutral-900 rounded-lg overflow-hidden flex flex-col h-72 bg-[#040611]">
      <div className="flex flex-wrap gap-2 p-2 border-b border-neutral-900 text-[10px] tracking-[0.15em] uppercase">
        {Array.from(statuses.entries()).map(([source, status]) => {
          const badge = sourceBadge(source.replace(/^pipeline:/, ''))
          const stateColor =
            status.state === 'finished'
              ? 'bg-emerald-500'
              : status.state === 'failed'
                ? 'bg-rose-500'
                : status.state === 'started'
                  ? 'bg-amber-500 animate-pulse'
                  : 'bg-neutral-700'
          return (
            <span
              key={source}
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium ${badge.color}`}
              title={status.error ?? status.state}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${stateColor}`} aria-hidden />
              {badge.label}
            </span>
          )
        })}
        {statuses.size === 0 && (
          <span className="text-neutral-600 px-2 py-0.5">No scrape running</span>
        )}
      </div>
      <div
        ref={consoleRef}
        className="flex-1 overflow-auto font-mono text-[11px] p-2 selectable"
      >
        {logs.length === 0 ? (
          <div className="text-neutral-700">stdout will stream here…</div>
        ) : (
          logs.map((log, i) => (
            <div
              key={i}
              className={
                log.stream === 'stderr' ? 'text-rose-300' : 'text-neutral-400'
              }
            >
              <span className="text-neutral-600">[{log.source}]</span> {log.line}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
