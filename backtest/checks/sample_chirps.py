"""Sample CHIRPS daily means for the Nyando plain and two headwater boxes.

The geotiffs are not stored. This writes backtest/checks/chirps_daily_means.csv.
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import urllib.request
from pathlib import Path

import numpy as np
import rasterio

BOXES = {
    "kano_plain": (34.85, -0.28, 35.10, -0.05),
    "nandi_tinderet": (35.05, 0.00, 35.40, 0.25),
    "kericho_mau": (35.15, -0.45, 35.50, -0.15),
}
OUT = Path(__file__).with_name("chirps_daily_means.csv")
FIELDS = ["date", *BOXES, *(f"{name}_n" for name in BOXES)]


def days() -> list[dt.date]:
    windows = (
        (dt.date(2020, 4, 1), dt.date(2020, 4, 26)),
        (dt.date(2024, 4, 20), dt.date(2024, 5, 8)),
    )
    found: list[dt.date] = []
    for start, end in windows:
        day = start
        while day <= end:
            found.append(day)
            day += dt.timedelta(days=1)
    return found


def fetch(day: dt.date) -> bytes:
    url = (
        "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_daily/tifs/p05/"
        f"{day.year}/chirps-v2.0.{day:%Y.%m.%d}.tif.gz"
    )
    last_error: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return gzip.decompress(response.read())
        except Exception as error:  # noqa: BLE001 - retry network reads
            last_error = error
    raise RuntimeError(f"failed to fetch {day}") from last_error


def sample(tif: bytes) -> dict[str, float | int]:
    values: dict[str, float | int] = {}
    with rasterio.open(io.BytesIO(tif)) as src:
        for name, bounds in BOXES.items():
            window = rasterio.windows.from_bounds(*bounds, transform=src.transform)
            data = src.read(1, window=window, boundless=True).astype("float64")
            data[data < 0] = np.nan
            values[name] = round(float(np.nanmean(data)), 2)
            values[f"{name}_n"] = int(np.isfinite(data).sum())
    return values


def load_done() -> dict[str, dict[str, str]]:
    if not OUT.exists():
        return {}
    with OUT.open(newline="", encoding="utf-8") as handle:
        return {row["date"]: row for row in csv.DictReader(handle)}


def write(rows: dict[str, dict[str, str]]) -> None:
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for day in sorted(rows):
            writer.writerow(rows[day])


def main() -> None:
    rows = load_done()
    for day in days():
        key = day.isoformat()
        if key in rows:
            print("have", key, flush=True)
            continue
        values = sample(fetch(day))
        rows[key] = {"date": key, **{field: values[field] for field in FIELDS if field != "date"}}
        write(rows)
        print(key, rows[key]["kano_plain"], rows[key]["nandi_tinderet"], rows[key]["kericho_mau"], flush=True)


if __name__ == "__main__":
    main()
