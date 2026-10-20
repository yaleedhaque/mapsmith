# Architecture

```
        ┌──────────┐   queries    ┌───────────────┐
        │  cli.py  │─────────────▶│  scraper.py   │  list → detail → reviews → menu
        └──────────┘              └───────┬───────┘
              │                           │
       queue.py (many areas)              │ uses
              │                           ▼
              │                   ┌───────────────┐    DOM logic
              │                   │  engine.py    │───────────────┐
              │                   │  (Playwright) │               │
              │                   └───────┬───────┘               ▼
              │                           │              extractors/
              │                           │              list.js detail.js
              │                           │              reviews.js menu.js
              ▼                           ▼
        config.py  ◀── config.json   ┌───────────────┐
        (delays, concurrency,        │   store.py    │  atomic JSON job + resume
         categories, headless)       │  Job / markers│  markers per place/step
                                     └───────┬───────┘
                                             ▼
                                        export.py → CSV / JSON / NDJSON / SQLite
```

## Design decisions

- **JS extractors, kept in JS.** Selectors change constantly; being able to paste
  an extractor into DevTools and iterate is worth more than a Python port. They
  ship as package data and are injected with `page.evaluate("async () => { … }")`.
- **`ftid` (Google CID) is the identity.** Every dedupe/merge keys on it, so the
  same place found by two queries collapses to one row.
- **Resume is per place per step.** A 3-hour detail pass that dies at place 400
  resumes at 400, not 0. Step completion is recorded in the job file *after* the
  work, and each write is atomic (`tmp` + `os.replace`).
- **Headless by default, media blocked.** On a small machine this is the
  difference between running and swapping. `--headful` for debugging.
- **Threads, not asyncio.** Playwright sync API + a small `ThreadPoolExecutor`
  gets useful parallelism with far less complexity than an async rewrite. Keep
  concurrency at 1–2 on low-RAM boxes.
- **Playwright `evaluate()` takes no `timeout=`.** (A real bug paid for once — the
  call raises `TypeError` and silently swallows to `None`.) Long-running
  extractors self-limit via their internal scroll loops instead.

## Resume semantics

`Job.pending(step)` returns places not yet flagged `_done_<step>`; `Job.is_done`
records step completion. The two levels mean:

- re-running an area never re-does finished steps;
- an interrupted step re-does only the unfinished places.

## Extending

- **New field:** add it to `extractors/detail.js` and to `export.COLUMNS`.
- **New phase:** write `extractors/<name>.js`, add a `*_phase` in `scraper.py`,
  register it in `scraper.PHASES` and `queue.STEPS`.
- **Proxy/grid support** (not yet implemented): the natural place is `Engine` —
  `browser.new_context(proxy=…)` and a grid driver that feeds `list_phase`
  generated cell queries.
