# Third-party licenses & attribution

mapsmith is MIT-licensed. It depends on, and takes inspiration from, the
following:

## Runtime dependency

| Project | License | Use |
|---|---|---|
| [Playwright for Python](https://github.com/microsoft/playwright-python) | Apache-2.0 | headless browser automation |
| [Chromium](https://www.chromium.org/) (via Playwright) | BSD-3-Clause + others | the rendered browser |

Install Playwright's browser with `playwright install chromium`; it is not bundled.

## Prior art / inspiration

| Project | License | Note |
|---|---|---|
| [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) | MIT | A mature Go Maps scraper. mapsmith's README compares against it, and its "extract → CSV/JSON/SQLite" shape informed mapsmith's output design. **No code copied.** |

## Data-source guidance

For redistributable bulk seed data, prefer
[**Overture Maps**](https://overturemaps.org/) (CDLA-Permissive-2.0) and
[OpenStreetMap](https://www.openstreetmap.org/copyright) (ODbL) over scraped
Google content. Google Maps content is subject to Google's Terms of Service;
mapsmith does not claim any license to it.

## Notes

- No Google/third-party proprietary code, fonts, or assets are bundled.
- The extractor CSS selectors are facts about a public web page's DOM, not
  copied source.
