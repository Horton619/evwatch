import { ElectronAPI } from '@electron-toolkit/preload'
import type {
  ScrapeBatchCompleteEvent,
  ScrapeLogEvent,
  ScrapeStatusEvent,
  UpdateStatus,
} from './index'

export interface VenvInfo {
  pythonPath: string
  repoRoot: string
  found: boolean
}

export interface AppVersionInfo {
  version: string
  venv: VenvInfo
}

export interface EvwatchBridge {
  // App
  getVersion: () => Promise<AppVersionInfo>

  // Scrape queue
  startScrape: (
    mode: 'all' | 'blocked',
  ) => Promise<{ ok: boolean; queued: string[]; reason?: string }>
  cancelScrape: () => Promise<{ ok: boolean }>
  isScrapeRunning: () => Promise<{ running: boolean }>

  onScrapeStatus: (cb: (e: ScrapeStatusEvent) => void) => () => void
  onScrapeLog: (cb: (e: ScrapeLogEvent) => void) => () => void
  onScrapeBatchComplete: (cb: (e: ScrapeBatchCompleteEvent) => void) => () => void

  // Updater
  checkForUpdates: () => Promise<{ ok: boolean; message?: string }>
  downloadUpdate: () => Promise<{ ok: boolean; message?: string }>
  installUpdate: () => Promise<{ ok: true }>

  onUpdateStatus: (cb: (e: UpdateStatus) => void) => () => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    evwatch: EvwatchBridge
  }
}
