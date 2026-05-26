import { spawn, ChildProcess } from 'node:child_process'
import { EventEmitter } from 'node:events'
import { probeVenv, type VenvInfo } from './venv'

/**
 * All sources runnable from the Mac (SPEC §5.1). Order is the run order
 * for "all" mode: cheap first (eBay API), then the heavier Playwright
 * sources.
 */
export const ALL_SOURCES = [
  'ebay',
  'carvana',
  'craigslist',
  'autotempest',
  'cargurus',
  'autotrader',
  'cars_dot_com',
] as const

/**
 * "Blocked only" mode runs just the Playwright/residential-IP sources.
 * eBay has a real API and runs fine from GHA, so it's excluded.
 */
export const BLOCKED_SOURCES = [
  'carvana',
  'craigslist',
  'autotempest',
  'cargurus',
  'autotrader',
  'cars_dot_com',
] as const

/** Mac-only scrapers refuse to run without this env var (defense in depth). */
const MAC_ONLY = new Set(['cargurus', 'autotrader', 'cars_dot_com'])

/**
 * After scrapers finish we run baselines + deal detection so the local
 * Mac has fresh deal_tags. Crucially we DO NOT run send_digest from the
 * Mac — that's GHA's job; emailing from Dave's laptop at random times
 * would be weird.
 */
export const POST_PIPELINE = ['pipeline.update_baselines', 'pipeline.detect_deals'] as const

export type ScrapeMode = 'all' | 'blocked'

export interface ScrapeLogEvent {
  source: string
  stream: 'stdout' | 'stderr'
  line: string
}

export interface ScrapeStatusEvent {
  source: string
  state: 'started' | 'finished' | 'failed' | 'skipped'
  exitCode?: number | null
  error?: string
}

export interface BatchCompleteEvent {
  ok: boolean
  ran: string[]
  failed: string[]
}

export class ScrapeQueue extends EventEmitter {
  private running = false
  private cancelRequested = false
  private currentProcess: ChildProcess | null = null

  /**
   * Run a sequence of `python -m <module>` invocations. Streams every
   * stdout/stderr line via 'log' events, fires 'status' per source, and
   * emits 'batch-complete' when done (or cancelled).
   */
  async start(mode: ScrapeMode): Promise<{ ok: boolean; queued: string[]; reason?: string }> {
    if (this.running) {
      return { ok: false, queued: [], reason: 'already running' }
    }
    const venv = probeVenv()
    if (!venv.found) {
      return { ok: false, queued: [], reason: 'venv not found' }
    }

    const scrapers = mode === 'blocked' ? [...BLOCKED_SOURCES] : [...ALL_SOURCES]
    const modules = [...scrapers.map((s) => `scrapers.${s}`), ...POST_PIPELINE]
    this.running = true
    this.cancelRequested = false

    // Run sequentially, not parallel — cleaner log streams + simpler
    // state. Each invocation is its own python process.
    void this._runSequence(venv, scrapers, modules)

    return { ok: true, queued: modules }
  }

  cancel(): { ok: boolean } {
    if (!this.running) return { ok: false }
    this.cancelRequested = true
    if (this.currentProcess) {
      this.currentProcess.kill('SIGTERM')
    }
    return { ok: true }
  }

  isRunning(): boolean {
    return this.running
  }

  private async _runSequence(
    venv: VenvInfo,
    _scrapers: readonly string[],
    modules: readonly string[],
  ): Promise<void> {
    const ran: string[] = []
    const failed: string[] = []

    try {
      for (const mod of modules) {
        if (this.cancelRequested) {
          this.emit('status', { source: mod, state: 'skipped' } satisfies ScrapeStatusEvent)
          continue
        }
        const result = await this._runOne(venv, mod)
        if (result.ok) {
          ran.push(mod)
        } else {
          failed.push(mod)
          // For pipeline steps a failure is bad data — but we still want
          // to finish what we can. Scraper failures are already
          // continue-on-error in spirit.
        }
      }
    } finally {
      this.running = false
      this.currentProcess = null
      const event: BatchCompleteEvent = {
        ok: failed.length === 0,
        ran,
        failed,
      }
      this.emit('batch-complete', event)
    }
  }

  private _runOne(venv: VenvInfo, modulePath: string): Promise<{ ok: boolean }> {
    const sourceName = modulePath.replace(/^scrapers\./, '').replace(/^pipeline\./, 'pipeline:')
    return new Promise((resolve) => {
      const env: NodeJS.ProcessEnv = { ...process.env }
      // Mac-only scrapers require this flag to actually run.
      const bareName = modulePath.replace(/^scrapers\./, '')
      if (MAC_ONLY.has(bareName)) {
        env.EVWATCH_ALLOW_MAC_ONLY_SCRAPERS = '1'
      }

      const child = spawn(venv.pythonPath, ['-m', modulePath], {
        cwd: venv.repoRoot,
        env,
      })
      this.currentProcess = child

      this.emit('status', {
        source: sourceName,
        state: 'started',
      } satisfies ScrapeStatusEvent)

      const onLine = (stream: 'stdout' | 'stderr', buf: Buffer) => {
        const text = buf.toString('utf8')
        for (const line of text.split('\n')) {
          if (line.length === 0) continue
          this.emit('log', { source: sourceName, stream, line } satisfies ScrapeLogEvent)
        }
      }
      child.stdout?.on('data', (buf) => onLine('stdout', buf))
      child.stderr?.on('data', (buf) => onLine('stderr', buf))

      child.on('close', (code) => {
        const ok = code === 0
        this.emit('status', {
          source: sourceName,
          state: ok ? 'finished' : 'failed',
          exitCode: code,
        } satisfies ScrapeStatusEvent)
        resolve({ ok })
      })
      child.on('error', (err) => {
        this.emit('status', {
          source: sourceName,
          state: 'failed',
          error: err.message,
        } satisfies ScrapeStatusEvent)
        resolve({ ok: false })
      })
    })
  }
}
