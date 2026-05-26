import { app, BrowserWindow } from 'electron'
import { autoUpdater, type ProgressInfo, type UpdateInfo } from 'electron-updater'

/**
 * Forward every electron-updater event to the renderer over ONE channel.
 * Don't subscribe per-event in the renderer; let main fan-in.
 *
 * This matches the VEP-wide pattern in ~/.claude/CLAUDE.md:
 *   "Forward every electron-updater event to the renderer over ONE channel.
 *   Don't subscribe per-event in the renderer; let main fan-in."
 */
export type UpdateStatus =
  | { type: 'checking' }
  | { type: 'available'; version: string }
  | { type: 'not-available' }
  | {
      type: 'progress'
      percent: number
      bytesPerSecond: number
      transferred: number
      total: number
    }
  | { type: 'downloaded'; version: string }
  | { type: 'error'; message: string }

type WindowGetter = () => BrowserWindow | null

export function configureUpdater(getMainWindow: WindowGetter): void {
  // Friendlier UX defaults — never silently download in the background.
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  // Pipe electron-updater's logger into our app log (visible in
  // Console.app via os_log / via stdout in dev).
  autoUpdater.logger = {
    info: (msg: unknown) => console.log('[updater]', msg),
    warn: (msg: unknown) => console.warn('[updater]', msg),
    error: (msg: unknown) => console.error('[updater]', msg),
    debug: (msg: unknown) => console.debug('[updater]', msg),
  }

  const send = (payload: UpdateStatus) => {
    const w = getMainWindow()
    if (w && !w.isDestroyed()) {
      w.webContents.send('update-status', payload)
    }
  }

  autoUpdater.on('checking-for-update', () => send({ type: 'checking' }))
  autoUpdater.on('update-available', (info: UpdateInfo) =>
    send({ type: 'available', version: info.version }),
  )
  autoUpdater.on('update-not-available', () => send({ type: 'not-available' }))
  autoUpdater.on('download-progress', (p: ProgressInfo) =>
    send({
      type: 'progress',
      percent: p.percent,
      bytesPerSecond: p.bytesPerSecond,
      transferred: p.transferred,
      total: p.total,
    }),
  )
  autoUpdater.on('update-downloaded', (info: UpdateInfo) =>
    send({ type: 'downloaded', version: info.version }),
  )
  autoUpdater.on('error', (err) =>
    send({ type: 'error', message: err?.message || String(err) }),
  )

  // Atom-feed cache lag at launch: GitHub caches releases.atom for a few
  // minutes, so a release published just before app launch may miss the
  // initial check. Delay 60s; the manual button in Settings hits a
  // fresher endpoint anyway.
  if (app.isPackaged) {
    setTimeout(() => {
      autoUpdater.checkForUpdates().catch((err: Error) => {
        console.error('[updater] checkForUpdates failed', err)
        send({ type: 'error', message: err.message })
      })
    }, 60_000)
  }
}

export async function checkForUpdates(): Promise<{ ok: boolean; message?: string }> {
  try {
    await autoUpdater.checkForUpdates()
    return { ok: true }
  } catch (err) {
    return { ok: false, message: (err as Error).message }
  }
}

export async function downloadUpdate(): Promise<{ ok: boolean; message?: string }> {
  try {
    await autoUpdater.downloadUpdate()
    return { ok: true }
  } catch (err) {
    return { ok: false, message: (err as Error).message }
  }
}

export function installUpdate(): void {
  // No async wrap — quitAndInstall doesn't return.
  autoUpdater.quitAndInstall()
}
