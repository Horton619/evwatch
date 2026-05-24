"""evwatch post-scrape pipeline.

Runs in order after every scrape (SPEC §5.2):

1. :mod:`pipeline.detect_deals`     — tag listings with NEW_PRIORITY / PRICE_DROP / BELOW_MARKET / RECURRENT_LISTING
2. :mod:`pipeline.update_baselines` — recompute per-bucket median prices from last 60 days
3. :mod:`pipeline.build_trends`     — weekly aggregate stats per make/model
4. :mod:`pipeline.send_digest`      — compose and POST HTML email to Resend
5. :mod:`pipeline.record_run`       — log run + source health
"""
