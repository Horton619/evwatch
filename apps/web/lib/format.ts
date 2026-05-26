/** Small server-safe formatters. No locale dep beyond Intl. */

export function formatPrice(price: number | null | undefined): string {
  if (price == null) return "—";
  return `$${price.toLocaleString("en-US")}`;
}

export function formatMileage(m: number | null | undefined): string {
  if (m == null) return "—";
  return `${m.toLocaleString("en-US")} mi`;
}

export function formatDistance(d: number | null | undefined): string {
  if (d == null) return "—";
  return `${d} mi away`;
}

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const diffSec = (t - Date.now()) / 1000;
  const absSec = Math.abs(diffSec);
  if (absSec < 60) return rtf.format(Math.round(diffSec), "second");
  if (absSec < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (absSec < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  if (absSec < 86400 * 30) return rtf.format(Math.round(diffSec / 86400), "day");
  if (absSec < 86400 * 365) return rtf.format(Math.round(diffSec / (86400 * 30)), "month");
  return rtf.format(Math.round(diffSec / (86400 * 365)), "year");
}

export function formatYearMakeModel(
  year: number | null,
  make: string | null,
  model: string | null,
  trim?: string | null,
): string {
  const parts: string[] = [];
  if (year) parts.push(String(year));
  if (make) parts.push(make);
  if (model) parts.push(model);
  if (trim) parts.push(trim);
  return parts.join(" ") || "Unknown vehicle";
}

export function sourceBadge(source: string): { label: string; color: string } {
  // Tailwind-like inline color tokens — these are class names, not values.
  // Used by the UI to color a small chip per source.
  switch (source) {
    case "ebay":       return { label: "eBay",        color: "bg-blue-900/40 text-blue-200" };
    case "carmax":     return { label: "CarMax",      color: "bg-amber-900/40 text-amber-200" };
    case "carvana":    return { label: "Carvana",     color: "bg-emerald-900/40 text-emerald-200" };
    case "craigslist": return { label: "Craigslist",  color: "bg-purple-900/40 text-purple-200" };
    case "autotempest":return { label: "AutoTempest", color: "bg-rose-900/40 text-rose-200" };
    default:           return { label: source,        color: "bg-neutral-800 text-neutral-300" };
  }
}
