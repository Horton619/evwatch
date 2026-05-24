"""Deal detection.

Tags every listing in the current run with zero or more of: ``NEW_PRIORITY``,
``PRICE_DROP``, ``BELOW_MARKET``, ``RECURRENT_LISTING``. Thresholds come from
``config/watchlist.yml``. Reads from ``evwatch.listings`` + ``price_history``,
writes deal tags back to the run.
"""
