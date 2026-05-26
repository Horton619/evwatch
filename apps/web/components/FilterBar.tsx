import Link from "next/link";
import type { Filters } from "@/lib/filters";
import { hasAnyFilter } from "@/lib/filters";

interface Props {
  filters: Filters;
  makes: string[];
  models: Array<{ make: string; model: string }>;
}

const SOURCES = ["ebay", "carmax", "carvana", "craigslist", "autotempest"];

/**
 * Plain HTML form. Submits GET to `/`, which means every filter change is a
 * full server roundtrip (URL changes, page re-renders SSR). Per SPEC §5.6
 * we deliberately avoid client-side filtering to keep the anon key off the
 * wire.
 */
export function FilterBar({ filters, makes, models }: Props) {
  return (
    <form
      method="get"
      action="/"
      className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end"
    >
      <Field label="Make">
        <select
          name="make"
          defaultValue={filters.make ?? ""}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        >
          <option value="">Any</option>
          {makes.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Model">
        <select
          name="model"
          defaultValue={filters.model ?? ""}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        >
          <option value="">Any</option>
          {models.map((m) => (
            <option key={`${m.make}::${m.model}`} value={m.model}>
              {m.model}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Max price">
        <input
          type="number"
          name="maxPrice"
          defaultValue={filters.maxPrice ?? ""}
          placeholder="—"
          min={0}
          step={500}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        />
      </Field>

      <Field label="Max mileage">
        <input
          type="number"
          name="maxMileage"
          defaultValue={filters.maxMileage ?? ""}
          placeholder="—"
          min={0}
          step={5000}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        />
      </Field>

      <Field label="Max distance (mi)">
        <input
          type="number"
          name="maxDistance"
          defaultValue={filters.maxDistance ?? ""}
          placeholder="—"
          min={0}
          step={25}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        />
      </Field>

      <Field label="Source">
        <select
          name="source"
          defaultValue={filters.source ?? ""}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm"
        >
          <option value="">Any</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </Field>

      {/* Preserve quick + sort across filter submits */}
      {filters.quick && <input type="hidden" name="quick" value={filters.quick} />}
      {filters.sort !== "last_seen_desc" && (
        <input type="hidden" name="sort" value={filters.sort} />
      )}

      <div className="col-span-2 md:col-span-6 flex justify-between items-center gap-2 pt-1">
        {hasAnyFilter(filters) ? (
          <Link
            href="/"
            className="text-xs text-neutral-400 hover:text-neutral-200 underline underline-offset-4"
          >
            Clear filters
          </Link>
        ) : (
          <span />
        )}
        <button
          type="submit"
          className="bg-orange-500 hover:bg-orange-400 text-neutral-950 font-medium text-sm px-4 py-1.5 rounded"
        >
          Apply
        </button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[10px] tracking-[0.2em] uppercase text-neutral-500 mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}
