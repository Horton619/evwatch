import { formatRelativeTime } from "@/lib/format";

interface Row {
  source: string;
  ran_at: string;
  listings_found: number | null;
  error: string | null;
}

interface Props {
  rows: Row[];
}

/**
 * Compact source health strip. Color semantics from VEP global guidelines:
 * emerald = ok, amber = stale (ran > 36h ago), rose = error.
 */
export function SourceHealthFooter({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <div className="text-xs text-neutral-600">
        No source runs logged yet.
      </div>
    );
  }
  const now = Date.now();
  const STALE_MS = 36 * 60 * 60 * 1000;

  return (
    <div className="flex flex-wrap gap-3 text-xs">
      {rows.map((r) => {
        const t = Date.parse(r.ran_at);
        const stale = Number.isFinite(t) && now - t > STALE_MS;
        const dotColor = r.error
          ? "bg-rose-500"
          : stale
            ? "bg-amber-500"
            : "bg-emerald-500";
        const tooltip = r.error
          ? `Error: ${r.error}`
          : `${r.listings_found ?? 0} listings, ${formatRelativeTime(r.ran_at)}`;
        return (
          <div
            key={r.source}
            title={tooltip}
            className="inline-flex items-center gap-1.5 text-neutral-400"
          >
            <span className={`w-2 h-2 rounded-full ${dotColor}`} aria-hidden />
            <span className="font-mono">{r.source}</span>
            <span className="text-neutral-600">{formatRelativeTime(r.ran_at)}</span>
          </div>
        );
      })}
    </div>
  );
}
