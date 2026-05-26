import type { Listing } from "@evwatch/shared";
import {
  dealBadges,
  formatDistance,
  formatMileage,
  formatPrice,
  formatRelativeTime,
  formatYearMakeModel,
  sourceBadge,
} from "@/lib/format";

interface Props {
  listing: Listing;
}

/**
 * Desktop layout — table row. The parent table provides column structure
 * (see ListingsTable.tsx).
 */
export function ListingTableRow({ listing }: Props) {
  const badge = sourceBadge(listing.source);
  const badges = dealBadges(listing.deal_tags);
  return (
    <tr className="border-b border-neutral-900 hover:bg-neutral-900/50">
      <td className="py-3 pr-3">
        {listing.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={listing.thumbnail_url}
            alt=""
            width={96}
            height={72}
            loading="lazy"
            className="w-24 h-18 object-cover rounded bg-neutral-900"
          />
        ) : (
          <div className="w-24 h-18 rounded bg-neutral-900 border border-neutral-800" />
        )}
      </td>
      <td className="py-3 pr-3">
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-neutral-100 hover:text-orange-400 font-medium"
        >
          {formatYearMakeModel(listing.year, listing.make, listing.model, listing.trim)}
        </a>
        <div className="text-xs text-neutral-500 mt-0.5">
          {listing.location ?? "—"}
        </div>
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {badges.map((b) => (
              <span
                key={b.label}
                title={b.detail}
                className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border ${b.color}`}
              >
                {b.label}
              </span>
            ))}
          </div>
        )}
      </td>
      <td className="py-3 pr-3 text-orange-400 font-medium tabular-nums">
        {formatPrice(listing.price)}
      </td>
      <td className="py-3 pr-3 text-neutral-300 tabular-nums">
        {formatMileage(listing.mileage)}
      </td>
      <td className="py-3 pr-3 text-neutral-400 tabular-nums">
        {formatDistance(listing.miles_from_port_orchard)}
      </td>
      <td className="py-3 pr-3">
        <span
          className={`inline-flex px-2 py-0.5 rounded text-[11px] font-medium ${badge.color}`}
        >
          {badge.label}
        </span>
      </td>
      <td className="py-3 pr-3 text-neutral-500 text-xs">
        {formatRelativeTime(listing.last_seen_at)}
      </td>
    </tr>
  );
}

/**
 * Mobile layout — card. Used below the md breakpoint.
 */
export function ListingCard({ listing }: Props) {
  const badge = sourceBadge(listing.source);
  const badges = dealBadges(listing.deal_tags);
  return (
    <a
      href={listing.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block border border-neutral-800 hover:border-neutral-600 rounded-lg p-3 transition-colors"
    >
      <div className="flex gap-3">
        {listing.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={listing.thumbnail_url}
            alt=""
            width={96}
            height={72}
            loading="lazy"
            className="w-24 h-18 object-cover rounded bg-neutral-900 flex-shrink-0"
          />
        ) : (
          <div className="w-24 h-18 rounded bg-neutral-900 border border-neutral-800 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="font-medium text-neutral-100 truncate">
            {formatYearMakeModel(listing.year, listing.make, listing.model, listing.trim)}
          </div>
          <div className="text-orange-400 font-semibold tabular-nums mt-0.5">
            {formatPrice(listing.price)}
          </div>
          <div className="text-xs text-neutral-500 mt-1 tabular-nums">
            {formatMileage(listing.mileage)} · {formatDistance(listing.miles_from_port_orchard)}
          </div>
          {badges.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {badges.map((b) => (
                <span
                  key={b.label}
                  title={b.detail}
                  className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border ${b.color}`}
                >
                  {b.label}
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between mt-2">
            <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-medium ${badge.color}`}>
              {badge.label}
            </span>
            <span className="text-[11px] text-neutral-500">
              {formatRelativeTime(listing.last_seen_at)}
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}
