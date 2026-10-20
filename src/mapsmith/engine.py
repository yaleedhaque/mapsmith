"""The headless browser engine.

One Playwright browser per run. Pages are created per task and closed after;
with ``concurrency > 1`` the detail phase fans out over a small page pool.

Why headless: the headed-Chrome route costs ~1.7 GB RAM per Maps tab; headless
Chromium with images/fonts/media blocked is ~5x lighter and on a small machine
is the difference between running and swapping.
"""

from __future__ import annotations

import random
import time
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .config import Config

_BLOCK = {"image", "font", "media"}


def _extractors_dir() -> Path:
    root = resources.files("mapsmith").joinpath("extractors")
    # works for both installed package and source checkout
    if hasattr(root, "__fspath__"):
        return Path(str(root))
    return Path(str(root))  # pragma: no cover


def load_js(name: str) -> str:
    """Load an extractor script (``list``, ``detail``, ``reviews``, ``menu``)."""
    return (_extractors_dir() / f"{name}.js").read_text(encoding="utf-8")


class Engine:
    """Owns the Playwright browser + context for one run."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._pw = None
        self.browser: Browser | None = None
        self._scripts = {n: load_js(n) for n in ("list", "detail", "reviews", "menu")}

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "Engine":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        self._pw = sync_playwright().start()
        launch_kwargs: dict = dict(
            headless=self.cfg.headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        if self.cfg.chrome_channel:
            launch_kwargs["channel"] = self.cfg.chrome_channel
        if self.cfg.browser == "chrome":
            launch_kwargs.setdefault("channel", "chrome")
        self.browser = self._pw.chromium.launch(**launch_kwargs)

    def stop(self) -> None:
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()
            self.browser = None
            self._pw = None

    # -- contexts / pages --------------------------------------------------

    def _context(self) -> BrowserContext:
        assert self.browser is not None, "Engine.start() was not called"
        ctx = self.browser.new_context(
            locale=self.cfg.locale,
            viewport={"width": 1280, "height": 900},
            user_agent=self.cfg.user_agent or (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
        )
        block = set(_BLOCK) if self.cfg.block_images else {"font", "media"}

        def route(route_):
            try:
                route_.abort() if route_.request.resource_type in block else route_.continue_()
            except Exception:
                pass

        ctx.route("**/*", route)
        return ctx

    @contextmanager
    def page(self):
        ctx = self._context()
        pg = ctx.new_page()
        try:
            yield pg
        finally:
            try:
                pg.close()
            finally:
                ctx.close()

    # -- navigation + extraction ------------------------------------------

    def goto(self, pg: Page, url: str) -> bool:
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=self.cfg.timeout_ms)
            return True
        except Exception:
            return False

    def extract(self, pg: Page, name: str) -> dict | None:
        """Run extractor *name* on the current page and return its JSON value."""
        js = self._scripts[name]
        try:
            return pg.evaluate("async () => { " + js + " }")
        except Exception:
            return None

    def sleep(self, base: float | None = None) -> None:
        d = (base if base is not None else self.cfg.per_place_delay)
        time.sleep(max(0.0, d + random.uniform(-self.cfg.jitter, self.cfg.jitter)))
