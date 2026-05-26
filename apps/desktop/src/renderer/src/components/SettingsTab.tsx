import { useEffect, useState } from 'react'
import type { UpdateStatus } from '../../../preload/index'
import { formatBytes, formatETA, formatSpeed } from '../lib/format'

// Derive types from the bridge API. Avoids importing from the preload
// .d.ts directly (which lives in a separate tsconfig project).
type AppVersionInfo = Awaited<ReturnType<typeof window.evwatch.getVersion>>
type VenvInfo = AppVersionInfo['venv']

interface Props {
  updateStatus: UpdateStatus | null
}

export function SettingsTab({ updateStatus }: Props): React.JSX.Element {
  const [versionInfo, setVersionInfo] = useState<AppVersionInfo | null>(null)
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    window.evwatch.getVersion().then(setVersionInfo)
  }, [])

  const onCheck = async () => {
    setChecking(true)
    await window.evwatch.checkForUpdates()
    setChecking(false)
  }

  const onDownload = async () => {
    await window.evwatch.downloadUpdate()
  }

  const onInstall = async () => {
    await window.evwatch.installUpdate()
  }

  return (
    <div className="space-y-6 selectable">
      <Card title="Updates">
        <div className="space-y-3">
          <div className="text-sm">
            Current version:{' '}
            <span className="font-mono text-neutral-200">
              v{versionInfo?.version ?? '…'}
            </span>
          </div>
          <UpdateStatusLine status={updateStatus} />
          {updateStatus?.type === 'progress' && (
            <div>
              <div className="h-1.5 bg-neutral-900 rounded overflow-hidden">
                <div
                  className="h-full bg-orange-500 transition-all"
                  style={{ width: `${updateStatus.percent}%` }}
                />
              </div>
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={onCheck}
              disabled={checking}
              className="text-sm px-3 py-1.5 rounded border border-neutral-700 hover:border-neutral-500 disabled:opacity-50"
            >
              {checking ? 'Checking…' : 'Check for updates'}
            </button>
            {updateStatus?.type === 'available' && (
              <button
                onClick={onDownload}
                className="text-sm px-3 py-1.5 rounded bg-orange-500 text-neutral-950 font-medium hover:bg-orange-400"
              >
                Download v{updateStatus.version}
              </button>
            )}
            {updateStatus?.type === 'downloaded' && (
              <button
                onClick={onInstall}
                className="text-sm px-3 py-1.5 rounded bg-orange-500 text-neutral-950 font-medium hover:bg-orange-400"
              >
                Install & restart
              </button>
            )}
          </div>
        </div>
      </Card>

      <Card title="Python venv">
        <VenvBlock info={versionInfo?.venv ?? null} />
      </Card>

      <Card title="About">
        <div className="text-xs text-neutral-500 leading-relaxed">
          <div>Visual Entropy Productions</div>
          <div>
            Source:{' '}
            <a
              href="https://github.com/Horton619/evwatch"
              target="_blank"
              rel="noopener noreferrer"
              className="text-neutral-400 hover:text-neutral-200 underline"
            >
              github.com/Horton619/evwatch
            </a>
          </div>
        </div>
      </Card>
    </div>
  )
}

function Card({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <section className="border border-neutral-900 rounded-lg p-4">
      <h3 className="text-[10px] tracking-[0.2em] uppercase text-neutral-500 mb-3">
        {title}
      </h3>
      {children}
    </section>
  )
}

function UpdateStatusLine({
  status,
}: {
  status: UpdateStatus | null
}): React.JSX.Element {
  if (!status) return <div className="text-sm text-neutral-500">—</div>
  switch (status.type) {
    case 'checking':
      return (
        <div className="text-sm text-neutral-400">
          Checking GitHub Releases…
        </div>
      )
    case 'not-available':
      return (
        <div className="text-sm text-emerald-300">
          You have the latest version.
        </div>
      )
    case 'available':
      return (
        <div className="text-sm text-neutral-200">
          Update available: v{status.version}
        </div>
      )
    case 'progress': {
      const remaining =
        status.bytesPerSecond > 0
          ? (status.total - status.transferred) / status.bytesPerSecond
          : 0
      return (
        <div className="text-sm text-neutral-300 font-mono tabular-nums">
          {Math.round(status.percent)}% · {formatBytes(status.transferred)} /{' '}
          {formatBytes(status.total)} · {formatSpeed(status.bytesPerSecond)}
          {status.bytesPerSecond > 0 && ` · ${formatETA(remaining)}`}
        </div>
      )
    }
    case 'downloaded':
      return (
        <div className="text-sm text-orange-300">
          v{status.version} ready — restart to install (banner above).
        </div>
      )
    case 'error':
      return (
        <div className="text-sm text-rose-300 font-mono break-all">
          Update error: {status.message}
        </div>
      )
  }
}

function VenvBlock({ info }: { info: VenvInfo | null }): React.JSX.Element {
  if (!info) return <div className="text-sm text-neutral-500">—</div>
  if (!info.found) {
    return (
      <div className="text-sm text-amber-300 leading-relaxed">
        venv not found. Scrape Now will fail until you create one at{' '}
        <code className="font-mono text-neutral-300">~/evwatch/venv</code> or
        set the <code className="font-mono">EVWATCH_VENV</code> env var.
      </div>
    )
  }
  return (
    <div className="text-xs space-y-1 font-mono">
      <div>
        <span className="text-neutral-500">python:</span>{' '}
        <span className="text-neutral-300 break-all">{info.pythonPath}</span>
      </div>
      <div>
        <span className="text-neutral-500">repo:</span>{' '}
        <span className="text-neutral-300 break-all">{info.repoRoot}</span>
      </div>
    </div>
  )
}
