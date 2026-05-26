import type { UpdateStatus } from '../../../preload/index'

interface Props {
  status: UpdateStatus | null
  onRestart: () => void
  onDismiss: () => void
}

/**
 * Top-of-window banner shown when an update has been downloaded and is
 * ready to install. Matches the VEP-wide pattern (~/.claude/CLAUDE.md
 * "In-app auto-update" section).
 */
export function UpdateBanner({
  status,
  onRestart,
  onDismiss,
}: Props): React.JSX.Element | null {
  if (status?.type !== 'downloaded') return null
  return (
    <div className="bg-orange-500/90 text-neutral-950 px-4 py-2 flex items-center justify-between text-sm font-medium">
      <span>
        evwatch v{status.version} is ready. Restart to finish updating.
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={onRestart}
          className="px-3 py-1 bg-neutral-950 text-orange-400 rounded hover:bg-neutral-900"
        >
          Restart now
        </button>
        <button
          onClick={onDismiss}
          className="px-2 py-1 hover:bg-orange-400 rounded"
          aria-label="Dismiss"
          title="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
