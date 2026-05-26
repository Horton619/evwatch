import Link from "next/link";
import type { Filters, Quick } from "@/lib/filters";
import { toQuery } from "@/lib/filters";

interface Props {
  filters: Filters;
}

const CHIPS: Array<{ value: Quick | null; label: string }> = [
  { value: null,       label: "All" },
  { value: "today",    label: "New today" },
  { value: "priority", label: "Priority hits" },
];

export function QuickFilters({ filters }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {CHIPS.map(({ value, label }) => {
        const active = filters.quick === value;
        const href = `/${toQuery(filters, { quick: value, page: 1 })}`;
        return (
          <Link
            key={label}
            href={href}
            className={[
              "inline-flex items-center px-3 py-1.5 rounded-full text-sm border transition-colors",
              active
                ? "bg-orange-500 border-orange-500 text-neutral-950 font-medium"
                : "border-neutral-700 text-neutral-300 hover:border-neutral-500 hover:text-neutral-100",
            ].join(" ")}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
