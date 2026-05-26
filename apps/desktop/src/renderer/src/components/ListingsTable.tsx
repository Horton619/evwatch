import type { Listing } from '@evwatch/shared'
import { ListingTableRow } from './ListingRow'

interface Props {
  rows: Listing[]
  emptyHint?: string
}

export function ListingsTable({ rows, emptyHint }: Props): React.JSX.Element {
  if (rows.length === 0) {
    return (
      <div className="border border-neutral-800 rounded-lg py-12 text-center text-neutral-500">
        {emptyHint ?? 'No listings yet.'}
      </div>
    )
  }
  return (
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[10px] tracking-[0.2em] uppercase text-neutral-500 border-b border-neutral-800 sticky top-0 bg-[#070910] z-[1]">
            <th className="py-2 pr-3 font-medium w-20"></th>
            <th className="py-2 pr-3 font-medium">Vehicle</th>
            <th className="py-2 pr-3 font-medium">Price</th>
            <th className="py-2 pr-3 font-medium">Mileage</th>
            <th className="py-2 pr-3 font-medium">Distance</th>
            <th className="py-2 pr-3 font-medium">Source</th>
            <th className="py-2 pr-3 font-medium">Last seen</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <ListingTableRow key={r.id} listing={r} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
