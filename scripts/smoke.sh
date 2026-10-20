#!/usr/bin/env bash
# mapsmith — one-shot local smoke test.
# Scrapes one small area, exports every format, and prints the row counts.
# Needs: an activated venv with `pip install -e .` and `playwright install chromium`.
set -euo pipefail

AREA="${1:-Bogura}"
OUT="${2:-data/raw}"

mapsmith list  --area "$AREA" --out "$OUT" --queries "tea stall"
mapsmith detail --area "$AREA" --out "$OUT" --limit 5
mapsmith export --out "$OUT" --export-out out --format all

python3 - "$OUT" <<'PY'
import json, sys, sqlite3
from pathlib import Path
out = Path(sys.argv[1])
jobs = [json.loads(p.read_text()) for p in out.glob("*.json")]
places = sum(len(j.get("places", [])) for j in jobs)
print(f"job files: {len(jobs)}  places: {places}")
db = Path("out/mapsmith.sqlite")
if db.exists():
    con = sqlite3.connect(db)
    print("sqlite rows:", con.execute("select count(*) from places").fetchone()[0])
PY
echo "OK -> $OUT + out/"
