import { existsSync } from 'node:fs'
import path from 'node:path'
import { app } from 'electron'

/**
 * Probe filesystem for the evwatch Python venv. evwatch ships as a thin
 * Electron wrapper around the repo's scrapers/ + pipeline/ packages; the
 * venv that runs them stays at the repo's `venv/` and is NOT bundled
 * into the dmg (SPEC §10: app is single-Mac, never distributed).
 *
 * Resolution order:
 *   1. EVWATCH_VENV env var (explicit override for power users)
 *   2. <repo>/venv when running via `pnpm dev:desktop`
 *   3. ~/evwatch/venv (the conventional checkout location for Dave)
 */
export interface VenvInfo {
  pythonPath: string
  repoRoot: string
  found: boolean
}

function tryPath(p: string): VenvInfo | null {
  const py = path.join(p, 'venv', 'bin', 'python')
  if (existsSync(py)) {
    return { pythonPath: py, repoRoot: p, found: true }
  }
  return null
}

export function probeVenv(): VenvInfo {
  // 1. Explicit override.
  const override = process.env.EVWATCH_VENV
  if (override) {
    const py = path.join(override, 'bin', 'python')
    if (existsSync(py)) {
      return {
        pythonPath: py,
        repoRoot: path.dirname(override),
        found: true,
      }
    }
  }

  // 2. Dev mode: app source lives inside the repo.
  // out/main/index.js → ../.. is apps/desktop → ../../../.. is repo root.
  const fromAppPath = path.resolve(app.getAppPath(), '..', '..')
  const dev = tryPath(fromAppPath)
  if (dev) return dev

  // 3. Conventional install location.
  const home = app.getPath('home')
  const conventional = path.join(home, 'evwatch')
  const inst = tryPath(conventional)
  if (inst) return inst

  return {
    pythonPath: '',
    repoRoot: '',
    found: false,
  }
}
