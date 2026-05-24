"""Baseline recomputation.

Recomputes ``evwatch.baselines`` rows keyed by
``(model, year_bucket, mileage_bucket, region)``. Uses the last 60 days of
observations from both live and Wayback-seeded data. Mixed-source baselines
are acceptable as long as ``comp_count`` is tracked accurately (see SPEC §6).
"""
