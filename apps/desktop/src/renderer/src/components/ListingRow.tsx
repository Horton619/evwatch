import type { Listing } from '@evwatch/shared'
import {
  dealBadges,
  formatDistance,
  formatMileage,
  formatPrice,
  formatRelativeTime,
  formatYearMakeModel,
  sourceBadge,
} from '../lib/format'

interface Props {
  listing: Listing
}

export function ListingTableRow({ listing }: Props): React.JSX.Element {
  const badge = sourceBadge(listing.source)
  const badges = dealBadges(listing.deal_tags)
  return (
    <tr className="border-b border-neutral-900 hover:bg-neutral-900/40 selectable">
      <td className="py-2 pr-3">
        {listing.thumbnail_url ? (
          <img
            src={listing.thumbnail_url}
            alt=""
            width={80}
            height={60}
            loading="lazy"
            className="w-20 h-14 object-cover rounded bg-neutral-900"
          />
        ) : (
          <div className="w-20 h-14 rounded bg-neutral-900 border border-neutral-800" />
        )}
      </td>
      <td className="py-2 pr-3 max-w-[280px]">
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-neutral-100 hover:text-orange-400 font-medium truncate block"
        >
          {formatYearMakeModel(listing.year, listing.make, listing.model, listing.trim)}
        </a>
        <div className="text-xs text-neutral-500 mt-0.5 truncate">
          {listing.location ?? '—'}
        </div>
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
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
      <td className="py-2 pr-3 text-orange-400 font-medium tabular-nums">
        {formatPrice(listing.price)}
      </td>
      <td className="py-2 pr-3 text-neutral-300 tabular-nums">
        {formatMileage(listing.mileage)}
      </td>
      <td className="py-2 pr-3 text-neutral-400 tabular-nums">
        {formatDistance(listing.miles_from_port_orchard)}
      </td>
      <td className="py-2 pr-3">
        <span
          className={`inline-flex px-2 py-0.5 rounded text-[11px] font-medium ${badge.color}`}
        >
          {badge.label}
        </span>
      </td>
      <td className="py-2 pr-3 text-neutral-500 text-xs">
        {formatRelativeTime(listing.last_seen_at)}
      </td>
    </tr>
  )
}
