import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/**
 * Supabase anon client for the renderer. Per SPEC §7 point 11, the anon
 * key is baked into the desktop build via Vite-injected env (VITE_*
 * vars). Defense-in-depth: RLS still enforces read-only at the database
 * level even though the key reaches the renderer process.
 *
 * Set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY in:
 *   - apps/desktop/.env (local dev, gitignored)
 *   - release-desktop.yml env vars (CI builds)
 */
const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const ANON = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

type EvwatchClient = SupabaseClient<any, 'evwatch', any>

let _client: EvwatchClient | null = null

export function getSupabase(): EvwatchClient {
  if (_client) return _client
  if (!URL || !ANON) {
    throw new Error(
      'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. ' +
        'Create apps/desktop/.env from .env.example before running pnpm dev:desktop.',
    )
  }
  _client = createClient<any, 'evwatch', any>(URL, ANON, {
    auth: { persistSession: false, autoRefreshToken: false },
    db: { schema: 'evwatch' },
  })
  return _client
}

export function isConfigured(): boolean {
  return Boolean(URL && ANON)
}
