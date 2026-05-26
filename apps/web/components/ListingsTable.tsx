import Link from "next/link";
import type { Listing } from "@evwatch/shared";
import type { Filters, Sort } from "@/lib/filters";
import { toQuery } from "@/lib/filters";
import { ListingCard, ListingTableRow } from "./ListingRow";

interface Props {
  rows: Listing[];
  filters: Filters;
}

const HEADERS: Array<{
  label: string;
  sort?: { asc: Sort; desc: Sort };
}> = [
  { label: "" },                                              // thumbnail column, not sortable
  { label: "Vehicle" },                                       // could sort by year, but column is mixed
  { label: "Price",   sort: { asc: "price_asc",   desc: "price_desc"  } },
  { label: "Mileage", sort: { asc: "mileage_asc", desc: "mileage_asc" } },
  { label: "Distance" },
  { label: "Source" },
  { label: "Last seen", sort: { asc: "last_seen_desc", desc: "last_seen_desc" } },
];

function sortArrow(filters: Filters, target: Sort | undefined): string {
  if (!target) return "";
  if (filters.sort === "year_desc" && target === "last_seen_desc") return "";
  if (filters.sort === target) {
    return target.endsWith("_asc") ? " ↑" : " ↓";
  }
  return "";
}

export function ListingsTable({ rows, filters }: Props) {
  if (rows.length === 0) {
    return (
      <div className="border border-neutral-800 rounded-lg py-16 text-center">
        <p className="text-neutral-400">No listings match these filters.</p>
        <Link
          href="/"
          className="inline-block mt-3 text-sm text-orange-400 hover:text-orange-300 underline underline-offset-4"
        >
          Clear filters
        </Link>
      </div>
    );
  }

  return (
    <>
      {/* Desktop: table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] tracking-[0.2em] uppercase text-neutral-500 border-b border-neutral-800">
              {HEADERS.map((h, i) => {
                if (!h.sort) {
                  return (
                    <th key={i} className="py-2 pr-3 font-medium">
                      {h.label}
                    </th>
                  );
                }
                const nextSort =
                  filters.sort === h.sort.asc ? h.sort.desc : h.sort.asc;
                const href = `/${toQuery(filters, { sort: nextSort, page: 1 })}`;
                return (
                  <th key={i} className="py-2 pr-3 font-medium">
                    <Link href={href} className="hover:text-neutral-200">
                      {h.label}
                      <span className="text-orange-400">{sortArrow(filters, h.sort.asc)}{sortArrow(filters, h.sort.desc)}</span>
                    </Link>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <ListingTableRow key={r.id} listing={r} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: cards */}
      <div className="md:hidden space-y-2">
        {rows.map((r) => (
          <ListingCard key={r.id} listing={r} />
        ))}
      </div>
    </>
  );
}
