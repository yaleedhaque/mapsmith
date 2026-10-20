"""Offline unit tests — no network, no browser.

Covers the resume store (the part that must never silently break) and the flat
exporter. Run: pytest -q
"""

from __future__ import annotations

import json

from mapsmith.config import Config
from mapsmith.export import COLUMNS, export, flatten
from mapsmith.store import Job


def test_slug_and_queries():
    cfg = Config()
    assert cfg.slug("Dhanmondi, Dhaka") == "dhanmondi--dhaka"
    qs = cfg.queries("Bogura")
    assert "restaurants in Bogura" in qs
    assert all("Bogura" in q for q in qs)


def test_job_resume_markers(tmp_path):
    p = tmp_path / "bogura.json"
    job = Job(p, slug="bogura", area="Bogura")
    job.upsert_place("0x1:0x2", {"name": "A", "url": "https://x"})
    assert len(job.pending("detail")) == 1
    job.mark_place_done("0x1:0x2", "detail")
    assert job.pending("detail") == []
    job.mark_done("detail")
    assert job.is_done("detail")

    # reload from disk -> resume state preserved
    job2 = Job(p, slug="bogura")
    assert job2.count() == 1
    assert job2.is_done("detail")
    assert job2.pending("detail") == []


def test_upsert_is_idempotent(tmp_path):
    job = Job(tmp_path / "a.json", slug="a")
    job.upsert_place("0x1:0x2", {"name": "A", "rating": 4.0})
    job.upsert_place("0x1:0x2", {"rating": 4.5})
    assert job.count() == 1
    assert job.place("0x1:0x2")["rating"] == 4.5
    assert job.place("0x1:0x2")["name"] == "A"


def test_corrupt_file_starts_clean(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    job = Job(p, slug="bad")
    assert job.count() == 0


def test_flatten_and_export(tmp_path):
    job = Job(tmp_path / "bogura.json", slug="bogura")
    job.upsert_place("0x1:0x2", {
        "name": "A", "url": "https://x", "rating": 4.5,
        "photos": ["p1", "p2"], "reviews": [{"author": "z", "stars": 5}],
        "_query": "cafes",
    })
    rows = [flatten(place) for place in job.places()]
    assert set(COLUMNS) - {"ftid"} <= set(rows[0])
    assert json.loads(rows[0]["photos"]) == ["p1", "p2"]
    assert rows[0]["search_category"] == "cafes"

    written = export([job.data], tmp_path / "out", fmt="all", stem="t")
    names = {w.name for w in written}
    assert names == {"t.csv", "t.json", "t.ndjson", "t.sqlite"}
    assert (tmp_path / "out" / "t.sqlite").exists()
