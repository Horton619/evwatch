-- Phase 5: persisted deal tags.
--
-- detect_deals.py writes a JSONB blob of tags onto each listing after every
-- pipeline run. The dashboard reads them directly — no recompute on render.
-- Shape:
--   {
--     "NEW_PRIORITY":  {},
--     "BELOW_MARKET":  { "pct_below": 0.164, "dollars_below": 5500,
--                        "baseline_median": 33500, "comp_count": 31 },
--     "PRICE_DROP":    { "previous_price": 35000, "delta": -1500,
--                        "delta_pct": -0.043,
--                        "observed_at_previous": "2026-05-19T..." }
--   }
--
-- Tags are recomputed for every listing on every pipeline run; stale tags
-- get cleared at run start and re-written from scratch.

alter table evwatch.listings
  add column if not exists deal_tags jsonb;

-- GIN index so the dashboard can do `deal_tags ? 'BELOW_MARKET'` cheaply.
create index if not exists listings_deal_tags_gin
  on evwatch.listings using gin (deal_tags);
