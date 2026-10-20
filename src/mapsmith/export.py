"""Export job JSON → CSV / JSON / NDJSON / SQLite.

One flat record per place. Nested values (reviews, photos, menu images,
order_online, popular_items) are JSON-encoded into the cell, so every output is
lossless relative to the job file.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable

# Column order for CSV / SQLite (superset of what any phase fills).
COLUMNS = [
    "ftid", "name", "name_local", "category", "address", "phone", "website",
    "lat", "lng", "plus_code", "located_in", "rating", "review_count",
    "price_level", "price_per_person", "hours", "service_options",
    "menu_url", "menu_text", "menu_images", "photos", "photo_count",
    "popular_items", "order_online", "reviews", "search_category", "url",
]

_NESTED = {"hours", "service_options", "menu_images", "photos", "popular_items",
           "order_online", "reviews"}


def flatten(place: dict) -> dict:
    """Normalize a job place into the flat export row."""
    row = {}
    for col in COLUMNS:
        if col == "ftid":
            row[col] = place.get("_ftid") or place.get("ftid")
        elif col == "url":
            row[col] = place.get("_url") or place.get("url")
        elif col == "search_category":
            row[col] = place.get("_query")
        else:
            row[col] = place.get(col)
    row["review_count_scraped"] = place.get("review_count_scraped")
    if row["menu_text"] and len(row["menu_text"]) > 5000:
        row["menu_text"] = row["menu_text"][:5000]
    for col in _NESTED:
        if isinstance(row.get(col), (list, dict)):
            row[col] = json.dumps(row[col], ensure_ascii=False)
    return row


def _iter_rows(jobs: Iterable[dict]) -> list[dict]:
    rows = []
    for job in jobs:
        for p in job.get("places", []):
            rows.append(flatten(p))
    return rows


def export_csv(rows: list[dict], path: Path) -> None:
    cols = COLUMNS + ["review_count_scraped"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def export_json(rows: list[dict], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def export_ndjson(rows: list[dict], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def export_sqlite(rows: list[dict], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    cols = COLUMNS + ["review_count_scraped"]
    con.execute("DROP TABLE IF EXISTS places")
    con.execute("CREATE TABLE places (" + ", ".join(f'"{c}" TEXT' for c in cols) + ", UNIQUE(ftid) ON CONFLICT REPLACE)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON places(name)")
    ph = ",".join("?" for _ in cols)
    con.executemany(
        f'INSERT OR REPLACE INTO places ({",".join(chr(34)+c+chr(34) for c in cols)}) VALUES ({ph})',
        [[r.get(c) for c in cols] for r in rows],
    )
    con.commit()
    con.close()


def export(jobs: Iterable[dict], out_dir: Path, fmt: str = "all", stem: str = "mapsmith") -> list[Path]:
    """Write the requested formats; returns the paths written."""
    rows = _iter_rows(jobs)
    out_dir = Path(out_dir)
    written: list[Path] = []
    formats = ["csv", "json", "ndjson", "sqlite"] if fmt == "all" else [fmt]
    for f in formats:
        if f == "csv":
            p = out_dir / f"{stem}.csv"; export_csv(rows, p); written.append(p)
        elif f == "json":
            p = out_dir / f"{stem}.json"; export_json(rows, p); written.append(p)
        elif f == "ndjson":
            p = out_dir / f"{stem}.ndjson"; export_ndjson(rows, p); written.append(p)
        elif f == "sqlite":
            p = out_dir / f"{stem}.sqlite"; export_sqlite(rows, p); written.append(p)
        else:
            raise ValueError(f"unknown format: {f}")
    return written
