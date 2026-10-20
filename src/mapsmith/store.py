"""Tiny JSON file store with per-step resume markers.

Every area/query job keeps one JSON file. Each step (list/detail/reviews/menu)
is merged into that file and recorded in a ``_steps`` map, so a crashed or
killed run resumes exactly where it stopped instead of re-walking the area.

The marker is written *after* the work it describes, and every write is
atomic (tmp file + rename) so a kill mid-write cannot leave a half file.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def atomic_write(path: Path, payload: Any) -> None:
    """Write JSON to *path* atomically (same-dir temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Job:
    """One resumable job file for an area/query slug.

    Layout::

        {
          "slug": "dhanmondi",
          "area": "Dhanmondi, Dhaka",
          "source": "google_maps",
          "retrieved": "...",
          "steps": {"list": "...", "detail": "..."},
          "places":  [ {..card.., "_ftid": "...", "_done_detail": true, ...} ]
        }
    """

    STEPS = ("list", "detail", "reviews", "menu")

    def __init__(self, path: Path, slug: str, area: str | None = None) -> None:
        self.path = Path(path)
        self.slug = slug
        self.data: dict[str, Any] = {
            "slug": slug,
            "area": area or slug,
            "source": "google_maps",
            "retrieved": None,
            "steps": {},
            "places": [],
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass  # corrupt/partial file -> start clean rather than crash

    # -- place index -------------------------------------------------------

    def _index(self) -> dict[str, dict]:
        return {p["_ftid"]: p for p in self.data.get("places", []) if p.get("_ftid")}

    def upsert_place(self, ftid: str | None, fields: dict[str, Any]) -> None:
        """Merge *fields* into the place keyed by *ftid* (or name fallback)."""
        if not ftid:
            return
        idx = self._index()
        row = idx.get(ftid, {"_ftid": ftid})
        row.update(fields)
        idx[ftid] = row
        self.data["places"] = list(idx.values())

    def place(self, ftid: str) -> dict | None:
        return self._index().get(ftid)

    def places(self) -> list[dict]:
        return self.data.get("places", [])

    def pending(self, step: str) -> list[dict]:
        """Places that still need *step* (skips ones already marked done)."""
        flag = f"_done_{step}"
        need_url = step in ("detail", "reviews", "menu")
        return [p for p in self.places()
                if p.get("_ftid") and not p.get(flag) and (p.get("url") if need_url else True)]

    # -- step markers ------------------------------------------------------

    def is_done(self, step: str) -> bool:
        return step in self.data.get("steps", {})

    def mark_done(self, step: str, count: int | None = None) -> None:
        self.data.setdefault("steps", {})[step] = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": count if count is not None else len(self.places()),
        }
        self.save()

    def mark_place_done(self, ftid: str, step: str) -> None:
        idx = self._index()
        row = idx.get(ftid)
        if row is not None:
            row[f"_done_{step}"] = True
            idx[ftid] = row
            self.data["places"] = list(idx.values())

    def count(self) -> int:
        return len(self.places())

    def save(self) -> None:
        self.data["retrieved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.data["count"] = self.count()
        atomic_write(self.path, self.data)
