import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

/**
 * Typed bridge exposed as `window.evwatch.*`. Two shapes:
 *  - request/response → `ipcRenderer.invoke`
 *  - main→renderer broadcast → `.on(...)` returning an unsubscriber
 */
const evwatch = {
  // -- App / venv ---------------------------------------------------------
  getVersion: () => ipcRenderer.invoke('app:get-version'),

  // -- Scrape queue -------------------------------------------------------
  startScrape: (mode: 'all' | 'blocked') =>
    ipcRenderer.invoke('scrape:start', { mode }),
  cancelScrape: () => ipcRenderer.invoke('scrape:cancel'),
  isScrapeRunning: () => ipcRenderer.invoke('scrape:is-running'),

  onScrapeStatus: (cb: (e: ScrapeStatusEvent) => void) => {
    const listener = (_: unknown, payload: ScrapeStatusEvent) => cb(payload)
    ipcRenderer.on('scrape-status', listener)
    return () => ipcRenderer.removeListener('scrape-status', listener)
  },
  onScrapeLog: (cb: (e: ScrapeLogEvent) => void) => {
    const listener = (_: unknown, payload: ScrapeLogEvent) => cb(payload)
    ipcRenderer.on('scrape-log', listener)
    return () => ipcRenderer.removeListener('scrape-log', listener)
  },
  onScrapeBatchComplete: (cb: (e: ScrapeBatchCompleteEvent) => void) => {
    const listener = (_: unknown, payload: ScrapeBatchCompleteEvent) =>
      cb(payload)
    ipcRenderer.on('scrape-batch-complete', listener)
    return () => ipcRenderer.removeListener('scrape-batch-complete', listener)
  },

  // -- Updater ------------------------------------------------------------
  checkForUpdates: () => ipcRenderer.invoke('update:check'),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.invoke('update:install'),

  onUpdateStatus: (cb: (e: UpdateStatus) => void) => {
    const listener = (_: unknown, payload: UpdateStatus) => cb(payload)
    ipcRenderer.on('update-status', listener)
    return () => ipcRenderer.removeListener('update-status', listener)
  },
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('evwatch', evwatch)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.evwatch = evwatch
}

// -- Event payload types (mirrored in index.d.ts for the renderer) --------

export interface ScrapeStatusEvent {
  source: string
  state: 'started' | 'finished' | 'failed' | 'skipped'
  exitCode?: number | null
  error?: string
}

export interface ScrapeLogEvent {
  source: string
  stream: 'stdout' | 'stderr'
  line: string
}

export interface ScrapeBatchCompleteEvent {
  ok: boolean
  ran: string[]
  failed: string[]
}

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
