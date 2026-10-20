"""The four scrape phases: list → detail → reviews → menu.

Each phase is pure: it takes an :class:`Engine`, a :class:`Job` and a
:class:`Config`, does its work, merges results into the job and marks progress
per place. The CLI wires them together and the queue reuses them.
"""

from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config
from .engine import Engine
from .store import Job


def _stars(value) -> float | None:
    if not value:
        return None
    m = re.search(r"([\d.]+)", str(value))
    return float(m.group(1)) if m else None


# --------------------------------------------------------------------------- list

def list_phase(engine: Engine, job: Job, cfg: Config, area: str, queries: list[str] | None = None) -> int:
    """Search each query and merge unique result cards into the job by CIDs."""
    queries = queries or cfg.queries(area)
    seen = {p["_ftid"] for p in job.places()}
    added = 0
    with engine.page() as pg:
        for q in queries:
            url = "https://www.google.com/maps/search/" + urllib.parse.quote(q) + "?hl=en"
            if not engine.goto(pg, url):
                print(f"  ! query failed: {q}")
                continue
            engine.sleep(cfg.per_query_delay)
            res = engine.extract(pg, "list") or {}
            n = 0
            for card in res.get("cards", []):
                ft = card.get("ftid")
                if ft and ft not in seen:
                    seen.add(ft)
                    card["_query"] = q
                    job.upsert_place(ft, card)
                    n += 1
            added += n
            print(f"  {q}: +{n} (total {job.count()})")
            engine.sleep(cfg.per_query_delay)
    job.mark_done("list", job.count())
    return added


# ------------------------------------------------------------------------- detail

def _detail_one(engine: Engine, job: Job, cfg: Config, place: dict) -> tuple[str, dict | None]:
    ftid = place["_ftid"]
    with engine.page() as pg:
        if not engine.goto(pg, place["url"]):
            return ftid, None
        engine.sleep(cfg.per_place_delay)
        d = engine.extract(pg, "detail") or {}
        if not d.get("name"):
            return ftid, None
        d["_url"] = place["url"]
        d["_card_lines"] = place.get("lines")
        return ftid, d


def detail_phase(engine: Engine, job: Job, cfg: Config, limit: int = 0) -> int:
    """Visit each pending place page and merge its details."""
    todo = job.pending("detail")
    if limit:
        todo = todo[:limit]
    if not todo:
        job.mark_done("detail", job.count())
        return 0
    done = 0
    if cfg.concurrency > 1:
        with ThreadPoolExecutor(max_workers=cfg.concurrency) as ex:
            futs = [ex.submit(_detail_one, engine, job, cfg, p) for p in todo]
            for fut in as_completed(futs):
                ftid, d = fut.result()
                if d:
                    job.upsert_place(ftid, d)
                    job.mark_place_done(ftid, "detail")
                    done += 1
                if done % 5 == 0:
                    job.save()
                    print(f"  {done} details…")
    else:
        with engine.page() as pg:
            for p in todo:
                if not engine.goto(pg, p["url"]):
                    continue
                engine.sleep(cfg.per_place_delay)
                d = engine.extract(pg, "detail") or {}
                if d.get("name"):
                    d["_url"] = p["url"]
                    d["_card_lines"] = p.get("lines")
                    job.upsert_place(p["_ftid"], d)
                    job.mark_place_done(p["_ftid"], "detail")
                    done += 1
                    if done % 5 == 0:
                        job.save()
                        print(f"  {done} details…")
                else:
                    print(f"  ! no data for {p.get('name')!r}")
    job.mark_done("detail", job.count())
    return done


# ------------------------------------------------------------------------ reviews

def reviews_phase(engine: Engine, job: Job, cfg: Config, limit: int = 0) -> int:
    """Open each pending place, click Reviews, capture up to ``max_reviews``."""
    todo = job.pending("reviews")
    if limit:
        todo = todo[:limit]
    if not todo:
        job.mark_done("reviews", job.count())
        return 0
    done = 0
    with engine.page() as pg:
        for p in todo:
            if not engine.goto(pg, p["url"]):
                continue
            engine.sleep(cfg.per_place_delay)
            v = engine.extract(pg, "reviews") or {}
            cards = (v.get("cards") or [])[: cfg.max_reviews]
            if cards:
                for r in cards:
                    r["stars"] = _stars(r.get("stars"))
            job.upsert_place(p["_ftid"], {"reviews": cards, "review_count_scraped": len(cards)})
            job.mark_place_done(p["_ftid"], "reviews")
            done += 1
            if done % 5 == 0:
                job.save()
                print(f"  {done} review sets…")
    job.mark_done("reviews", job.count())
    return done


# --------------------------------------------------------------------------- menu

def menu_phase(engine: Engine, job: Job, cfg: Config, limit: int = 0) -> int:
    """Open each pending place, click the Menu tab, capture photos + menu text."""
    todo = job.pending("menu")
    if limit:
        todo = todo[:limit]
    if not todo:
        job.mark_done("menu", job.count())
        return 0
    done = 0
    with engine.page() as pg:
        for p in todo:
            if not engine.goto(pg, p["url"]):
                continue
            engine.sleep(cfg.per_place_delay)
            m = engine.extract(pg, "menu") or {}
            job.upsert_place(p["_ftid"], {
                "menu_url": m.get("menu_url") or p.get("menu_url"),
                "menu_text": (m.get("menu_text") or "")[:3000],
                "menu_images": m.get("images", []),
            })
            job.mark_place_done(p["_ftid"], "menu")
            done += 1
            if done % 5 == 0:
                job.save()
                print(f"  {done} menus…")
    job.mark_done("menu", job.count())
    return done


PHASES = {"list": list_phase, "detail": detail_phase, "reviews": reviews_phase, "menu": menu_phase}
