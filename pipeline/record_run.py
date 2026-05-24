"""Run + source-health logging.

Writes one ``evwatch.digests`` row summarising the digest that was sent and
one ``evwatch.source_runs`` row per scraper invocation with duration,
listings_found, and any error message. Powers the ``/health`` dashboard page.
"""
