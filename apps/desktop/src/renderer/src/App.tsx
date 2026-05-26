import { useCallback, useEffect, useState } from 'react'
import { isConfigured } from './lib/supabase'
import { fetchDeals, fetchDrops, fetchLiveListings } from './lib/queries'
import { Sidebar } from './components/Sidebar'
import { ListingsTab } from './components/ListingsTab'
import { ScrapeConsole } from './components/ScrapeConsole'
import { SettingsTab } from './components/SettingsTab'
import { SourceLogTab } from './components/SourceLogTab'
import { UpdateBanner } from './components/UpdateBanner'
import type {
  ScrapeLogEvent,
  ScrapeStatusEvent,
  UpdateStatus,
} from '../../preload/index'

type TabKey = 'live' | 'deals' | 'drops' | 'trends' | 'log' | 'settings'

interface TabDef {
  key: TabKey
  label: string
}

const TABS: TabDef[] = [
  { key: 'live',     label: 'Live' },
  { key: 'deals',    label: 'Deals' },
  { key: 'drops',    label: 'Drops' },
  { key: 'trends',   label: 'Trends' },
  { key: 'log',      label: 'Source Log' },
  { key: 'settings', label: 'Settings' },
]

function App(): React.JSX.Element {
  const [tab, setTab] = useState<TabKey>('live')
  const [scraping, setScraping] = useState(false)
  const [scrapeMode, setScrapeMode] = useState<'all' | 'blocked' | null>(null)
  const [logs, setLogs] = useState<ScrapeLogEvent[]>([])
  const [statuses, setStatuses] = useState<Map<string, ScrapeStatusEvent>>(
    new Map(),
  )
  const [refreshTick, setRefreshTick] = useState(0)
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)

  // -- Subscribe to main-process broadcasts ---------------------------------
  useEffect(() => {
    const offStatus = window.evwatch.onScrapeStatus((e) => {
      setStatuses((prev) => {
        const next = new Map(prev)
        next.set(e.source, e)
        return next
      })
    })
    const offLog = window.evwatch.onScrapeLog((e) => {
      setLogs((prev) => [...prev.slice(-500), e])
    })
    const offBatch = window.evwatch.onScrapeBatchComplete(() => {
      setScraping(false)
      setScrapeMode(null)
      // Force every visible tab + sidebar to re-query.
      setRefreshTick((t) => t + 1)
    })
    const offUpdate = window.evwatch.onUpdateStatus((e) => {
      setUpdateStatus(e)
      if (e.type === 'downloaded') setBannerDismissed(false)
    })
    return () => {
      offStatus()
      offLog()
      offBatch()
      offUpdate()
    }
  }, [])

  // -- Scrape control -------------------------------------------------------
  const onScrapeNow = useCallback(async (mode: 'all' | 'blocked') => {
    setLogs([])
    setStatuses(new Map())
    setScrapeMode(mode)
    setScraping(true)
    const result = await window.evwatch.startScrape(mode)
    if (!result.ok) {
      setScraping(false)
      setScrapeMode(null)
      alert(`Couldn't start: ${result.reason}`)
    }
  }, [])
  const onCancelScrape = useCallback(async () => {
    await window.evwatch.cancelScrape()
  }, [])

  // -- Update banner --------------------------------------------------------
  const onRestart = useCallback(() => window.evwatch.installUpdate(), [])
  const onDismissBanner = useCallback(() => setBannerDismissed(true), [])

  if (!isConfigured()) {
    return <NotConfigured />
  }

  return (
    <div className="flex flex-col h-full">
      {!bannerDismissed && (
        <UpdateBanner
          status={updateStatus}
          onRestart={onRestart}
          onDismiss={onDismissBanner}
        />
      )}

      {/* Title bar (hidden inset style — leave room for traffic lights) */}
      <div className="h-10 flex items-center justify-between pl-20 pr-4 border-b border-neutral-900 select-none">
        <div className="flex items-baseline gap-2">
          <span className="text-[10px] tracking-[0.3em] uppercase text-neutral-500">
            Visual Entropy Productions
          </span>
          <span className="text-sm font-semibold text-neutral-100">evwatch</span>
        </div>
        <ConnectionPill />
      </div>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          scraping={scraping}
          scrapeMode={scrapeMode}
          onScrapeNow={onScrapeNow}
          onCancelScrape={onCancelScrape}
          refreshTick={refreshTick}
        />

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tab bar */}
          <div className="flex gap-0.5 px-4 pt-3 border-b border-neutral-900">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={[
                  'px-3 py-2 text-sm rounded-t border-b-2 transition-colors',
                  tab === t.key
                    ? 'border-orange-500 text-neutral-100 font-medium'
                    : 'border-transparent text-neutral-500 hover:text-neutral-300',
                ].join(' ')}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-hidden px-4 pb-4">
            <div className={`h-full ${scraping ? 'pb-2' : ''}`}>
              {tab === 'live' && (
                <ListingsTab fetcher={fetchLiveListings} refreshTick={refreshTick} />
              )}
              {tab === 'deals' && (
                <ListingsTab
                  fetcher={fetchDeals}
                  refreshTick={refreshTick}
                  emptyHint="No below-market listings right now. Try another tab or run Scrape Now."
                />
              )}
              {tab === 'drops' && (
                <ListingsTab
                  fetcher={fetchDrops}
                  refreshTick={refreshTick}
                  emptyHint="No recent price drops. Try another tab or run Scrape Now."
                />
              )}
              {tab === 'trends' && (
                <div className="border border-neutral-900 rounded-lg p-12 text-center text-neutral-500">
                  Trends view ships in Phase 8.
                </div>
              )}
              {tab === 'log' && <SourceLogTab refreshTick={refreshTick} />}
              {tab === 'settings' && (
                <SettingsTab updateStatus={updateStatus} />
              )}
            </div>

            {scraping && (
              <div className="mt-2">
                <ScrapeConsole logs={logs} statuses={statuses} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function ConnectionPill(): React.JSX.Element {
  return (
    <div className="flex items-center gap-2 text-xs text-neutral-500">
      <span className="w-2 h-2 rounded-full bg-emerald-500" />
      <span>Supabase</span>
    </div>
  )
}

function NotConfigured(): React.JSX.Element {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <p className="text-[10px] tracking-[0.3em] uppercase text-neutral-500">
          Visual Entropy Productions
        </p>
        <h1 className="text-2xl font-semibold text-neutral-100">
          evwatch
        </h1>
        <p className="text-sm text-neutral-400 leading-relaxed">
          Missing{' '}
          <code className="font-mono text-amber-400">VITE_SUPABASE_URL</code> or{' '}
          <code className="font-mono text-amber-400">VITE_SUPABASE_ANON_KEY</code>.
          Copy <code className="font-mono">apps/desktop/.env.example</code> to{' '}
          <code className="font-mono">apps/desktop/.env</code> and fill in the
          Flux project values, then restart.
        </p>
      </div>
    </div>
  )
}

export default App
