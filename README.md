# mapsmith

**A lightweight, headless, resume-first Google Maps scraper — CLI + library.**
Collect local-business leads (name, category, address, phone, website, rating,
coordinates), reviews, and — where Google exposes it — **menu-tab photos + menu
text**, into CSV / JSON / NDJSON / SQLite.

Built for the 7.5 GB laptop: headless Chromium with images/fonts/media blocked,
**~5× lighter** than a headed browser, and **resumable at two levels** so a crash
never costs more than the place in flight.

> ⚠️ **Scraping Google Maps is against Google's Terms of Service.** mapsmith is
> published for education, research and small-scale personal use. You are
> responsible for how you use the output and for complying with the law and
> Google's terms in your jurisdiction. See [Legal & ethics](#legal--ethics).

---

## Why another Maps scraper?

There is an excellent, mature tool for this job: **[gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)**
(Go, MIT, ~6.7k★). If you need **bulk lead-gen at high throughput with proxies and
Docker**, use it — it is faster and more battle-tested than mapsmith.

mapsmith exists for a different profile, and it does a few things gosom does not:

| | mapsmith | gosom/google-maps-scraper |
|---|---|---|
| Language / engine | Python + Playwright | Go + Playwright |
| Distribution | `pip install` | Docker image / Go binary |
| Throughput | modest, single box | **~120 places/min** (proxies) |
| **Menu-tab capture** (dish/menu **photos + menu text**) | **yes** | menu **link** only |
| **Headless, ultra-light mode** (blocks image/font/media) | **yes** | heavier browser |
| Resume granularity | **per place, per step** | per run (`-resume`) |
| Output | CSV / JSON / NDJSON / **SQLite** | CSV / JSON / Postgres / S3 / LeadsDB |
| Concurrency | threaded pages (small) | **worker pool (large)** |
| Proxy rotation | no | **yes** |
| Library use | **yes** (`from mapsmith import ...`) | CLI / API |

**Pick gosom** for volume, proxies, Postgres/Kubernetes. **Pick mapsmith** for a
small, readable, hackable Python library that also grabs menu photos and stays
gentle on a modest machine — or **use both**: mapsmith for detail/menu richness,
gosom for bulk breadth.

---

## Install

```bash
git clone https://github.com/yaleedhaque/mapsmith
cd mapsmith
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
playwright install chromium        # downloads the browser once
```

`pip install -e .` also installs the `mapsmith` console command.

## Quick start

```bash
# 1) search queries and collect result cards for one area
mapsmith list  --area "Dhanmondi, Dhaka"

# 2) visit each place page and extract details (+ reviews + menu)
mapsmith detail   --area "Dhanmondi, Dhaka"
mapsmith reviews  --area "Dhanmondi, Dhaka"
mapsmith menu     --area "Dhanmondi, Dhaka"

# or the whole pipeline in one go
mapsmith run --area "Dhanmondi, Dhaka" --with-reviews --with-menu

# 3) export everything to csv/json/ndjson/sqlite
mapsmith export --out data/raw --format all
```

Everything is keyed by the Google **CID** (`ftid`, the `0x…:0x…` token) and
written to one resumable job file per area: `data/raw/<slug>.json`. Kill it and
re-run the same command — it resumes.

### Many areas

```bash
mapsmith queue examples/areas.json --steps list,detail,reviews,menu
```

`areas.json` is just `[{"area": "...", "slug": "..."}]`. The queue skips any
step already marked done and survives one bad area without stopping.

## Customise

```bash
mapsmith init --file my.config.json     # then edit categories, delays, headless…
mapsmith list --area "Gulshan, Dhaka" --config my.config.json --out data/raw
```

Useful flags: `--headful` (watch the browser), `--concurrency 2` (parallel
detail pages), `--queries "dentists,pharmacies"` (override the category set),
`--limit N` (cap places per phase while testing).

## Output

One flat record per place. Nested values (reviews, photos, menu images,
order-online links, popular items) are JSON-encoded so the export is lossless.

| column | meaning |
|---|---|
| `ftid` | Google CID (`0x…:0x…`) — stable dedupe key |
| `name`, `name_local` | business name (+ local-script name when present) |
| `category`, `rating`, `review_count` | type and reputation |
| `address`, `phone`, `website`, `plus_code`, `located_in` | contact |
| `lat`, `lng` | coordinates |
| `hours`, `service_options` | opening hours, dine-in/takeaway/… |
| `price_level`, `price_per_person` | price band (currency-aware) |
| `photos`, `photo_count` | real place photos (reviewer avatars filtered out) |
| `menu_url`, `menu_text`, `menu_images` | **menu-tab** capture (when Google exposes it) |
| `popular_items`, `order_online` | dishes + delivery links |
| `reviews` | `[{author, stars, date, text}]` |

## Use as a library

```python
from mapsmith import Config
from mapsmith.engine import Engine
from mapsmith.store import Job
from mapsmith.scraper import list_phase, detail_phase

cfg = Config(headless=True, per_place_delay=2.5)
job = Job(cfg.path_for("Bogura"), slug="bogura", area="Bogura")

with Engine(cfg) as engine:
    list_phase(engine, job, cfg, "Bogura", queries=["tea stall in Bogura"])
    detail_phase(engine, job, cfg, limit=20)
    job.save()
```

## How it works

- **Engine** (`engine.py`) — one Playwright browser; headless Chromium with
  `image/font/media` blocked; a fresh context per page.
- **Extractors** (`extractors/*.js`) — the DOM logic for the results feed
  (`list`), a place page (`detail`), the Reviews tab (`reviews`) and the Menu tab
  (`menu`). Kept in JS so they can be developed in DevTools and shipped as-is.
- **Store** (`store.py`) — atomic JSON job file with per-place, per-step resume
  markers; duplicate places merge by `ftid`.
- **Phases** (`scraper.py`) — `list → detail → reviews → menu`, each skipping
  work already marked done.
- **Export** (`export.py`) — flat rows → CSV / JSON / NDJSON / SQLite.

**Locale note:** drive the flow from a *search* (`mapsmith list`) so the browser
session is English; opening a raw `/maps/place/` URL can geo-serve a non-English
UI where the English selectors miss.

## Limitations (honest)

- **Menu capture is best-effort.** Google removed the dedicated Menu tab for many
  places/locales; where it is absent (common for small eateries) `menu_images` is
  empty. That is expected, not a bug.
- **No proxy rotation** — large scrapes will hit rate limits/blocking. Use gosom
  for proxy-backed volume.
- **No exhaustive grid coverage** — mapsmith searches your query list; it does not
  tile a bounding box. Different guides are available at broad enquiry levels.
- Selectors track a moving Google DOM; they can break without warning. Fixes
  welcome.

## Legal & ethics

Scraping Google Maps violates Google's Terms of Service, and the legality of
scraping public data varies by country. mapsmith stores only what Google serves
publicly, does **not** bypass authentication or paywalls, and defaults to polite
delays — but **you** remain responsible for your use, for respecting
`robots.txt`/terms, for personal-data rules (GDPR/CCPA/etc.), and for any claim
arising from your scrape. For redistribution, prefer openly-licensed datasets
(e.g. **Overture Maps**) as a bulk seed. This notice is not legal advice.

## Contributing

Issues and PRs welcome — especially extractor fixes when Google's DOM shifts, and
proxy/grid support. See `docs/ARCHITECTURE.md`. Keep changes small, tested, and
honest about limitations.

## Credits

- Engine: [Playwright](https://playwright.dev). Prior art & inspiration:
  [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper).
- See [`THIRD_PARTY.md`](THIRD_PARTY.md) for licenses and attribution.

## License

MIT — see [`LICENSE`](LICENSE).

---

**Ads: 0 · Trackers: 0 · Cha: ∞.** Every coffee (bKash · Nagad · Rocket → `01730934983`) is one more bug fixed at 3 AM. ☕

<p align="center">
  <img src="docs/assets/signature.png" alt="Md. Yaleed Haque" width="220">
  <br>
  <sub>MAPSMITH · MAPS, MINED POLITELY</sub>
</p>
