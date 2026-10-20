"""Configuration for a mapsmith run.

Everything the scraper needs is here — selectors live in the JS extractors, but
pacing, blocking, browser selection and the default query set are config so the
tool is not welded to one dataset.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


# A generic food/nightlife-lead starter set. Override with your own --queries or
# a custom category list; `{area}` is substituted with the area name.
DEFAULT_CATEGORIES = [
    "restaurants", "cafes", "coffee shop", "fast food", "tea stall", "bakery",
    "sweet shop", "biryani", "Chinese restaurant", "juice bar", "street food",
    "pizza", "burger", "kebab", "shawarma", "dessert", "ice cream", "buffet",
    "vegetarian restaurant", "supermarket", "grocery store", "pharmacy",
    "hair salon", "gym", "hotel", "guest house", "clothing store", "electronics store",
]


@dataclass
class Config:
    """Per-run configuration."""

    out_dir: Path = Path("data/raw")
    headless: bool = True
    browser: str = "chromium"          # chromium | chrome
    chrome_channel: str | None = None   # e.g. "chrome" to use system Chrome
    block_images: bool = True
    concurrency: int = 1                # parallel detail workers (keep 1-2 on small boxes)
    per_query_delay: float = 2.0        # base seconds between list queries
    per_place_delay: float = 2.2        # base seconds between place pages
    jitter: float = 0.8                 # +/- random seconds added to delays
    timeout_ms: int = 45000             # page navigation timeout
    scroll_wait_ms: int = 900
    max_reviews: int = 60
    locale: str = "en-US"
    user_agent: str | None = None
    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))

    def queries(self, area: str) -> list[str]:
        out = []
        for c in self.categories:
            out.append(c if area.lower() in c.lower() else f"{c} in {area}")
        return out

    def slug(self, area: str) -> str:
        return "".join(ch if ch.isalnum() else "-" for ch in area.lower()).strip("-")

    def path_for(self, area: str) -> Path:
        return Path(self.out_dir) / f"{self.slug(area)}.json"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["out_dir"] = str(d["out_dir"])
        return d

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Config":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        raw["out_dir"] = Path(raw.get("out_dir", "data/raw"))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})
