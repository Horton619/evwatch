import "server-only";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.SUPABASE_URL;
const ANON = process.env.SUPABASE_ANON_KEY;

// The client's third generic narrows to whatever `db.schema` was passed.
// Pin to "evwatch" so .from() resolves against our schema without per-call
// .schema() chains.
type EvwatchClient = SupabaseClient<any, "evwatch", any>;

let _client: EvwatchClient | null = null;

/**
 * Server-side Supabase client scoped to the `evwatch` schema, authenticated
 * with the anon key. Reads only — writes happen from GHA + the desktop app
 * using the service role. Cached per process.
 *
 * SPEC §5.6: the anon key never reaches the browser. This module imports
 * `server-only` so a stray client-component import fails at build time.
 */
export function getSupabase(): EvwatchClient {
  if (_client) return _client;
  if (!URL || !ANON) {
    throw new Error(
      "Missing Supabase env vars. Set SUPABASE_URL and SUPABASE_ANON_KEY " +
        "in apps/web/.env.local (dev) or Vercel env (prod). " +
        "Do NOT prefix with NEXT_PUBLIC_ — see SPEC §7.",
    );
  }
  _client = createClient<any, "evwatch", any>(URL, ANON, {
    auth: { persistSession: false, autoRefreshToken: false },
    db: { schema: "evwatch" },
  });
  return _client;
}

export function isConfigured(): boolean {
  return Boolean(URL && ANON);
}
