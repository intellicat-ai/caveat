"""HTTP access for the authoring scripts: one cached, paced session.

Responses are cached under work/.cache/ (git-ignored), so a stage can be
re-run without repeating its requests. Settings come from the git-ignored
config/openalex.toml:

    [openalex]
    api_key = "..."            # sent as a bearer token to OpenAlex only
    max_requests_per_second = 10
    mailto = "you@example.org" # optional; enables Unpaywall and Crossref's polite pool

Nothing from the config is ever written to an output file.
"""
import time
import tomllib
from pathlib import Path

import requests
import requests_cache

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "config" / "openalex.toml"
CACHE = ROOT / "work" / ".cache" / "http"
USER_AGENT = "caveat-authoring (https://github.com/intellicat-ai/caveat)"


def load_config(path: Path = CONFIG) -> dict:
    if not path.exists():
        return {"api_key": "", "rate": 5.0, "mailto": ""}
    section = tomllib.loads(path.read_text()).get("openalex", {})
    return {
        "api_key": str(section.get("api_key", "")).strip(),
        "rate": float(section.get("max_requests_per_second", 5) or 5),
        "mailto": str(section.get("mailto", "")).strip(),
    }


class Client:
    """A paced session. cache=False is for requests that must not be cached
    (archive save requests, liveness checks)."""

    def __init__(self, config: dict | None = None, cache: bool = True, session=None):
        self.config = config or load_config()
        if session is not None:
            self.session = session
        elif cache:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            self.session = requests_cache.CachedSession(str(CACHE), backend="sqlite", expire_after=-1,
                                                        allowable_codes=(200, 404))
        else:
            self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0

    def _pace(self):
        gap = 1.0 / max(self.config["rate"], 0.1)
        wait = self._last + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get(self, url, params=None, headers=None, retries=4, **kw):
        for attempt in range(retries + 1):
            self._pace()
            r = self.session.get(url, params=params, headers=headers or {}, timeout=60, **kw)
            if r.status_code not in (429, 500, 502, 503, 504) or attempt == retries:
                return r
            time.sleep(min(2 ** attempt, 30))
        return r

    def json(self, url, params=None, headers=None):
        r = self.get(url, params=params, headers=headers)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
