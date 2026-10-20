"""mapsmith CLI — run, list, detail, reviews, menu, queue, export, init."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .engine import Engine
from .export import export
from .scraper import detail_phase, list_phase, menu_phase, reviews_phase
from .store import Job

LEGAL = (
    "NOTE: scraping Google Maps is against Google's Terms of Service. Use "
    "responsibly, at small scale, and only where you have the right to collect "
    "the data. You are responsible for how you use the output."
)


def _load_cfg(args) -> Config:
    cfg = Config.load(args.config) if getattr(args, "config", None) else Config()
    if getattr(args, "out", None):
        cfg.out_dir = Path(args.out)
    if getattr(args, "headful", False):
        cfg.headless = False
    if getattr(args, "concurrency", None):
        cfg.concurrency = args.concurrency
    if getattr(args, "queries", None):
        cfg.categories = [q.strip() for q in args.queries.split(",") if q.strip()]
    return cfg


def _open_job(cfg: Config, area: str) -> Job:
    return Job(cfg.path_for(area), slug=cfg.slug(area), area=area)


def cmd_list(args) -> int:
    cfg = _load_cfg(args)
    job = _open_job(cfg, args.area)
    with Engine(cfg) as engine:
        n = list_phase(engine, job, cfg, args.area)
    job.save()
    print(f"list: {n} new places -> {job.path} ({job.count()} total)")
    return 0


def cmd_detail(args) -> int:
    cfg = _load_cfg(args)
    job = _open_job(cfg, args.area)
    with Engine(cfg) as engine:
        n = detail_phase(engine, job, cfg, limit=args.limit)
    job.save()
    print(f"detail: {n} places -> {job.path}")
    return 0


def cmd_reviews(args) -> int:
    cfg = _load_cfg(args)
    job = _open_job(cfg, args.area)
    with Engine(cfg) as engine:
        n = reviews_phase(engine, job, cfg, limit=args.limit)
    job.save()
    print(f"reviews: {n} places -> {job.path}")
    return 0


def cmd_menu(args) -> int:
    cfg = _load_cfg(args)
    job = _open_job(cfg, args.area)
    with Engine(cfg) as engine:
        n = menu_phase(engine, job, cfg, limit=args.limit)
    job.save()
    print(f"menu: {n} places -> {job.path}")
    return 0


def cmd_run(args) -> int:
    """Full pipeline for one area."""
    cfg = _load_cfg(args)
    job = _open_job(cfg, args.area)
    with Engine(cfg) as engine:
        if not job.is_done("list"):
            list_phase(engine, job, cfg, args.area)
        if not job.is_done("detail"):
            detail_phase(engine, job, cfg, limit=args.limit)
        if args.with_reviews and not job.is_done("reviews"):
            reviews_phase(engine, job, cfg, limit=args.limit)
        if args.with_menu and not job.is_done("menu"):
            menu_phase(engine, job, cfg, limit=args.limit)
    job.save()
    print(f"run: {job.count()} places -> {job.path}")
    return 0


def cmd_queue(args) -> int:
    from .queue import main as queue_main
    return queue_main([args.areas, "--steps", args.steps,
                       *(["--config", args.config] if args.config else []),
                       *(["--out", args.out] if args.out else []),
                       *(["--limit", str(args.limit)] if args.limit else [])])


def cmd_export(args) -> int:
    cfg = _load_cfg(args)
    out_dir = Path(cfg.out_dir)
    if args.input:
        jobs = [json.loads(Path(args.input).read_text(encoding="utf-8"))]
    else:
        jobs = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(out_dir.glob("*.json"))
                if p.name not in ("areas.json",)]
    if not jobs:
        print(f"no job files in {out_dir}", file=sys.stderr)
        return 1
    written = export(jobs, Path(args.export_out or "out"), fmt=args.format, stem=args.stem)
    for p in written:
        print(f"wrote {p}")
    return 0


def cmd_init(args) -> int:
    cfg = _load_cfg(args)
    cfg.save(Path(args.file))
    print(f"wrote {args.file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mapsmith", description="Headless, resume-first Google Maps scraper.")
    ap.add_argument("--version", action="version", version=f"mapsmith {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common_io(p):
        p.add_argument("--area", required=True, help="e.g. 'Dhanmondi, Dhaka'")
        p.add_argument("--config", help="config JSON path")
        p.add_argument("--out", help="output dir (default data/raw)")
        p.add_argument("--headful", action="store_true", help="show the browser")
        p.add_argument("--concurrency", type=int, help="parallel detail workers")

    p = sub.add_parser("list", help="search queries, collect result cards")
    common_io(p); p.add_argument("--queries", help="comma-separated queries (else defaults)")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("detail", help="visit each place page, extract details")
    common_io(p); p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_detail)

    p = sub.add_parser("reviews", help="capture reviews for each place")
    common_io(p); p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_reviews)

    p = sub.add_parser("menu", help="capture menu-tab photos + text")
    common_io(p); p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_menu)

    p = sub.add_parser("run", help="full pipeline for one area")
    common_io(p); p.add_argument("--limit", type=int, default=0)
    p.add_argument("--with-reviews", action="store_true")
    p.add_argument("--with-menu", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("queue", help="run over many areas from areas.json")
    p.add_argument("areas", help="areas.json")
    p.add_argument("--steps", default="list,detail,reviews,menu")
    p.add_argument("--config"); p.add_argument("--out")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("export", help="export job JSON -> csv/json/ndjson/sqlite")
    p.add_argument("--input", help="single job json (else all in --out)")
    p.add_argument("--out", default="data/raw", help="where job files live")
    p.add_argument("--export-out", help="output directory (default out/)")
    p.add_argument("--format", default="all", choices=["all", "csv", "json", "ndjson", "sqlite"])
    p.add_argument("--stem", default="mapsmith")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("init", help="write a config.json")
    p.add_argument("--file", default="mapsmith.config.json")
    p.set_defaults(func=cmd_init)

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    print(LEGAL, file=sys.stderr)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
