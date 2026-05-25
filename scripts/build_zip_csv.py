"""One-shot generator for scrapers/data/us_zips_pnw.csv.

Pulls the public-domain GeoNames US postal-code dataset, filters to the states
within practical driving range of Port Orchard (WA, OR, ID, MT, CA, NV), and
writes a small CSV the scrapers can load at runtime without any network
dependency.

Re-run only when zip data drifts (rare) or when the geographic range needs
to change. Output is committed to the repo.

Usage:
    venv/bin/python scripts/build_zip_csv.py
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

# Permissive but bounded — Port Orchard sits at ~47.55N, -122.65W. WA + OR
# fully cover the 100-mile radius today. ID/MT/CA/NV are included so that if
# `radius_miles` is bumped or origin moves, we don't have to regenerate.
STATES = {"WA", "OR", "ID", "MT", "CA", "NV"}

GEONAMES_URL = "https://download.geonames.org/export/zip/US.zip"
OUT_PATH = Path(__file__).resolve().parents[1] / "scrapers" / "data" / "us_zips_pnw.csv"


def main() -> int:
    print(f"Downloading {GEONAMES_URL} ...")
    with urllib.request.urlopen(GEONAMES_URL, timeout=60) as resp:
        raw = resp.read()
    print(f"  {len(raw):,} bytes")

    rows: list[tuple[str, str, str, str, str]] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open("US.txt") as f:
            # GeoNames postal format (tab-separated, no header):
            #   country, postal, place, admin1, admin1_code,
            #   admin2, admin2_code, admin3, admin3_code,
            #   latitude, longitude, accuracy
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            for r in reader:
                if len(r) < 12:
                    continue
                state_code = r[4]
                if state_code not in STATES:
                    continue
                postal, place, lat, lon = r[1], r[2], r[9], r[10]
                if not (postal and lat and lon):
                    continue
                rows.append((postal, place, state_code, lat, lon))

    rows.sort(key=lambda r: r[0])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["zip", "city", "state", "lat", "lon"])
        w.writerows(rows)

    print(f"Wrote {len(rows):,} rows to {OUT_PATH.relative_to(OUT_PATH.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
