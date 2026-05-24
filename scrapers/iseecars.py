"""iSeeCars baseline seeder.

One-time + monthly HTML scrape of iSeeCars model pages for national and
regional EV depreciation curves. Used to seed ``evwatch.baselines`` with
synthetic rows (``comp_count = -1``) before enough live observations exist.
Run from the Mac, not GitHub Actions.
"""
