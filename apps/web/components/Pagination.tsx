import Link from "next/link";
import type { Filters } from "@/lib/filters";
import { PAGE_SIZE, toQuery } from "@/lib/filters";

interface Props {
  filters: Filters;
  total: number;
}

export function Pagination({ filters, total }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (totalPages <= 1) return null;

  const prevHref =
    filters.page > 1 ? `/${toQuery(filters, { page: filters.page - 1 })}` : null;
  const nextHref =
    filters.page < totalPages ? `/${toQuery(filters, { page: filters.page + 1 })}` : null;

  return (
    <div className="flex items-center justify-between text-sm text-neutral-400 pt-2">
      <div>
        Page {filters.page} of {totalPages} · {total.toLocaleString("en-US")} listings
      </div>
      <div className="flex gap-2">
        {prevHref ? (
          <Link
            href={prevHref}
            className="px-3 py-1 rounded border border-neutral-700 hover:border-neutral-500 hover:text-neutral-200"
          >
            ← Prev
          </Link>
        ) : (
          <span className="px-3 py-1 rounded border border-neutral-900 text-neutral-700">
            ← Prev
          </span>
        )}
        {nextHref ? (
          <Link
            href={nextHref}
            className="px-3 py-1 rounded border border-neutral-700 hover:border-neutral-500 hover:text-neutral-200"
          >
            Next →
          </Link>
        ) : (
          <span className="px-3 py-1 rounded border border-neutral-900 text-neutral-700">
            Next →
          </span>
        )}
      </div>
    </div>
  );
}
