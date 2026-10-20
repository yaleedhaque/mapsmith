#!/usr/bin/env python3
"""mapsmith queue — run list→detail→(reviews→menu) over many areas.

Resumable at two levels:
  * per area: an area is skipped only when its job file records every requested
    step as done (``job.is_done(step)``);
  * per step: within an area, an interrupted ``detail`` resumes at the first
    place without ``_done_detail`` — no full re-walk.

areas.json format::

    [{"area": "Dhanmondi, Dhaka", "slug": "dhanmondi-dhaka"},
     {"area": "Gulshan, Dhaka",  "slug": "gulshan-dhaka"}]

Run it detached and let it work; it logs one line per step.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .config import Config
from .engine import Engine
from .scraper import detail_phase, list_phase, menu_phase, reviews_phase
from .store import Job

STEPS = ("list", "detail", "reviews", "menu")


def log(msg: str, logfile: Path | None = None) -> None:
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg
    print(line, flush=True)
    if logfile:
        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def run_area(engine: Engine, cfg: Config, area: str, slug: str | None = None,
             steps: tuple[str, ...] = STEPS, limit: int = 0) -> dict:
    """Run (or resume) one area; returns a small per-area stats dict."""
    slug = slug or cfg.slug(area)
    job = Job(cfg.path_for(area), slug=slug, area=area)
    stats = {"slug": slug, "area": area}
    for step in steps:
        if job.is_done(step):
            log(f"  {slug}: {step} already done, skipping")
            continue
        started = time.time()
        if step == "list":
            n = list_phase(engine, job, cfg, area)
        elif step == "detail":
            n = detail_phase(engine, job, cfg, limit=limit)
        elif step == "reviews":
            n = reviews_phase(engine, job, cfg, limit=limit)
        elif step == "menu":
            n = menu_phase(engine, job, cfg, limit=limit)
        else:
            raise ValueError(step)
        job.save()
        stats[step] = n
        log(f"  {slug}: {step} done ({n}) in {time.time() - started:.0f}s")
    stats["places"] = job.count()
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run mapsmith over a queue of areas.")
    ap.add_argument("areas", help="areas.json (list of {area, slug})")
    ap.add_argument("--steps", default="list,detail,reviews,menu",
                    help="phases to run, comma-separated")
    ap.add_argument("--config", help="config JSON path")
    ap.add_argument("--out", help="output dir override")
    ap.add_argument("--limit", type=int, default=0, help="places per area per phase")
    ap.add_argument("--only", help="run a single area slug only")
    a = ap.parse_args(argv)

    cfg = Config.load(a.config) if a.config else Config()
    if a.out:
        cfg.out_dir = Path(a.out)
    steps = tuple(s.strip() for s in a.steps.split(",") if s.strip())

    areas = json.loads(Path(a.areas).read_text(encoding="utf-8"))
    if a.only:
        areas = [x for x in areas if (x.get("slug") or cfg.slug(x["area"])) == a.only]
    logfile = Path(cfg.out_dir) / "mapsmith-queue.log"

    with Engine(cfg) as engine:
        for item in areas:
            log(f"== {item.get('slug', cfg.slug(item['area']))} ({item['area']})", logfile)
            try:
                stats = run_area(engine, cfg, item["area"], item.get("slug"), steps, a.limit)
                log(f"== {stats['slug']}: {stats.get('places', 0)} places", logfile)
            except KeyboardInterrupt:
                log("interrupted — progress saved; re-run to resume", logfile)
                return 130
            except Exception as exc:  # keep the queue alive across one bad area
                log(f"!! {item.get('slug', item.get('area'))}: {exc!r}", logfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
