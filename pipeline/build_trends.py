"""Weekly trend aggregation.

Computes per-make/model weekly stats — median price, listing count, median
days on market — and writes to ``evwatch.trends_weekly``. Powers the
``/trends`` dashboard view and the Monday weekly-snapshot email section.
"""
