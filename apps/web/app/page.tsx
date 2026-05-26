import { FilterBar } from "@/components/FilterBar";
import { ListingsTable } from "@/components/ListingsTable";
import { Pagination } from "@/components/Pagination";
import { QuickFilters } from "@/components/QuickFilters";
import { SourceHealthFooter } from "@/components/SourceHealthFooter";
import { parseFilters, queryListings, querySourceHealth } from "@/lib/filters";
import { isConfigured } from "@/lib/supabase";
import { allMakes, allModels } from "@/lib/watchlist";

// Next 16: searchParams is async. Awaiting it makes the page dynamic
// automatically — no need for `export const dynamic`.
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function Home({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const filters = parseFilters(params);

  if (!isConfigured()) {
    return <NotConfigured />;
  }

  // Run both queries in parallel. Allow either to fail without nuking the
  // whole page render — source health is informational.
  const [listingsResult, sourceHealthResult] = await Promise.allSettled([
    queryListings(filters),
    querySourceHealth(),
  ]);

  if (listingsResult.status === "rejected") {
    return <QueryError message={String(listingsResult.reason?.message ?? listingsResult.reason)} />;
  }

  const { rows, total } = listingsResult.value;
  const sourceHealth =
    sourceHealthResult.status === "fulfilled" ? sourceHealthResult.value : [];

  const makes = allMakes();
  const models = allModels();

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">
      <QuickFilters filters={filters} />
      <FilterBar filters={filters} makes={makes} models={models} />
      <ListingsTable rows={rows} filters={filters} />
      <Pagination filters={filters} total={total} />
      <div className="pt-6 border-t border-neutral-900">
        <div className="text-[10px] tracking-[0.2em] uppercase text-neutral-500 mb-2">
          Source health
        </div>
        <SourceHealthFooter rows={sourceHealth} />
      </div>
    </div>
  );
}

function NotConfigured() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold text-neutral-100 mb-2">
        Dashboard not configured
      </h1>
      <p className="text-neutral-400 text-sm leading-relaxed">
        Missing <code className="font-mono text-amber-400">SUPABASE_URL</code> and{" "}
        <code className="font-mono text-amber-400">SUPABASE_ANON_KEY</code>. Add them to{" "}
        <code className="font-mono text-neutral-300">apps/web/.env.local</code> for
        local dev, or to the Vercel project's env vars for production. Don't prefix with{" "}
        <code className="font-mono">NEXT_PUBLIC_</code> — see{" "}
        <code className="font-mono text-neutral-300">SPEC.md §7</code>.
      </p>
    </div>
  );
}

function QueryError({ message }: { message: string }) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold text-neutral-100 mb-2">
        Couldn't reach Supabase
      </h1>
      <p className="text-neutral-400 text-sm leading-relaxed">
        {message}
      </p>
      <p className="text-neutral-500 text-xs mt-4">
        Check that the <code className="font-mono">evwatch</code> schema is in the
        project's <strong>Exposed Schemas</strong> list (Supabase dashboard → Project
        Settings → API).
      </p>
    </div>
  );
}
