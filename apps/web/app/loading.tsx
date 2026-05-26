export default function Loading() {
  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6 animate-pulse">
      {/* Quick filters */}
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 w-20 rounded-full bg-neutral-900" />
        ))}
      </div>

      {/* Filter bar */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-9 rounded bg-neutral-900" />
        ))}
      </div>

      {/* Table rows */}
      <div className="space-y-1">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-3 py-3 border-b border-neutral-900">
            <div className="w-24 h-18 rounded bg-neutral-900 flex-shrink-0" />
            <div className="flex-1 space-y-2 py-1">
              <div className="h-4 w-1/3 bg-neutral-900 rounded" />
              <div className="h-3 w-1/4 bg-neutral-900 rounded" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
