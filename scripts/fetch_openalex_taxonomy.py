#!/usr/bin/env python3
"""Fetch the OpenAlex topic taxonomy into mappings/openalex/.

Usage:
    python scripts/fetch_openalex_taxonomy.py --source api [--config PATH]
    python scripts/fetch_openalex_taxonomy.py --source jsonl --input FILE

--source api    pages /domains, /fields, /subfields and /topics with cursor
                paging. The API key is read from config/openalex.toml, which
                must be git-ignored (copy config/openalex.example.toml).
--source jsonl  reads raw OpenAlex objects, one per line, each with an extra
                "level" key (domain|field|subfield|topic). For offline use.

Writes:
    mappings/openalex/openalex-taxonomy.jsonl   normalized records
    mappings/openalex/manifest.json             provenance and counts
Then run scripts/build_openalex_mapping.py.

Normalization: OpenAlex values are taken as published except that
  * surrounding whitespace is stripped from every string;
  * the strings "nan", "null" and "none" (any case) mean "no value";
  * URL fields (wikidata, wikipedia) must start with http:// or https:// and
    have characters that are not allowed in IRIs percent-encoded; anything
    else is dropped.
Every change is counted in manifest.json under "normalization".

Politeness: OpenAlex rejects more than 100 requests per second and meters a
daily budget. This script sends one request at a time, paces requests to the
configured rate (default 5 per second, capped at 50), uses the maximum page
size of 100, and backs off exponentially on 429 and 5xx responses. The key
travels only in the Authorization header, never in a URL, and is never
printed or written to disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "mappings" / "openalex"
DEFAULT_CONFIG = REPO_ROOT / "config" / "openalex.toml"
API_BASE = "https://api.openalex.org"
USER_AGENT = "caveat-openalex-fetch/1 (+https://github.com/intellicat-ai/caveat)"
PER_PAGE = 100          # OpenAlex maximum
MAX_RATE = 50.0         # our ceiling; OpenAlex rejects > 100 requests/second
DEFAULT_RATE = 5.0
LEVELS = ["domain", "field", "subfield", "topic"]
ENDPOINT = {"domain": "domains", "field": "fields", "subfield": "subfields", "topic": "topics"}
PUBLISHED = {"domain": 4, "field": 26, "subfield": 252, "topic": 4516}
RETRY_STATUS = {429, 500, 502, 503, 504}
MISSING_TOKENS = {"nan", "null", "none"}
URL_FIELDS = ("wikidata", "wikipedia")
# Characters that may not appear in an IRI (RFC 3987) and that Turtle rejects.
IRI_UNSAFE = set(' "<>{}|\\^`') | {chr(c) for c in range(0x20)} | {chr(0x7f)}
NORMALIZATION_KINDS = ("stripped", "missing_token", "url_encoded", "url_dropped")


# --------------------------------------------------------------------------- config

def ensure_ignored(path: Path) -> None:
    """Refuse to read a key file that git would commit."""
    try:
        inside = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return
    if inside.returncode != 0:
        return
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(path)], check=False)
    if r.returncode != 0:
        raise SystemExit(f"{path} is not git-ignored; add it to .gitignore before storing a key in it")


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    if not path.exists():
        raise SystemExit(
            f"missing {path}: copy config/openalex.example.toml to {path} and put your "
            "OpenAlex API key in it (https://openalex.org/settings/api)")
    ensure_ignored(path)
    with open(path, "rb") as f:
        section = tomllib.load(f).get("openalex", {})
    key = str(section.get("api_key", "")).strip()
    if not key:
        raise SystemExit(f"no api_key in {path}: add your OpenAlex API key under [openalex]")
    rate = float(section.get("max_requests_per_second", DEFAULT_RATE))
    return {"api_key": key, "rate": rate}


def request_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT, "Accept": "application/json"}


def page_url(level: str, cursor: str) -> str:
    q = urllib.parse.urlencode({"per_page": PER_PAGE, "cursor": cursor})
    return f"{API_BASE}/{ENDPOINT[level]}?{q}"


# --------------------------------------------------------------------------- HTTP

class RateLimiter:
    def __init__(self, rate: float, clock=time.monotonic, sleep=time.sleep):
        if not 0 < rate <= MAX_RATE:
            raise ValueError(f"max_requests_per_second must be in (0, {MAX_RATE}], got {rate}")
        self.interval = 1.0 / rate
        self.clock, self.sleep = clock, sleep
        self.next_at = 0.0

    def wait(self) -> None:
        now = self.clock()
        if now < self.next_at:
            self.sleep(self.next_at - now)
            now = self.next_at
        self.next_at = now + self.interval


def _open(req: urllib.request.Request, timeout: int = 60):
    return urllib.request.urlopen(req, timeout=timeout)


def get_json(url: str, key: str, limiter: RateLimiter, tries: int = 6, sleep=time.sleep) -> tuple[dict, dict]:
    """GET url; return (json, headers). Never includes the key in errors."""
    for attempt in range(tries):
        limiter.wait()
        req = urllib.request.Request(url, headers=request_headers(key))
        try:
            with _open(req) as r:
                return json.loads(r.read().decode("utf-8")), dict(r.headers)
        except urllib.error.HTTPError as e:
            status = e.code
            retry_after = e.headers.get("Retry-After") if e.headers else None
            if status in RETRY_STATUS and attempt < tries - 1:
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                sleep(delay + random.uniform(0, 0.5))
                continue
            raise SystemExit(f"OpenAlex returned HTTP {status} for {url}") from None
        except urllib.error.URLError as e:
            if attempt < tries - 1:
                sleep(2 ** attempt + random.uniform(0, 0.5))
                continue
            raise SystemExit(f"network error for {url}: {e.reason}") from None
    raise SystemExit(f"giving up on {url}")


# --------------------------------------------------------------------------- records

def _id(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("id")
    if not v:
        return None
    return str(v).rstrip("/").rsplit("/", 1)[-1]


def new_stats() -> dict:
    return {k: {} for k in NORMALIZATION_KINDS}


def _count(stats: dict | None, kind: str, field: str) -> None:
    if stats is not None:
        stats[kind][field] = stats[kind].get(field, 0) + 1


def clean_str(value, field: str, stats: dict | None = None) -> str | None:
    if value is None:
        return None
    s = str(value)
    t = s.strip()
    if t != s:
        _count(stats, "stripped", field)
    if t.lower() in MISSING_TOKENS:
        _count(stats, "missing_token", field)
        return None
    return t or None


def clean_url(value, field: str, stats: dict | None = None) -> str | None:
    s = clean_str(value, field, stats)
    if s is None:
        return None
    if not s.lower().startswith(("http://", "https://")):
        _count(stats, "url_dropped", field)
        return None
    if any(ch in IRI_UNSAFE for ch in s):
        s = "".join(urllib.parse.quote(ch, safe="") if ch in IRI_UNSAFE else ch for ch in s)
        _count(stats, "url_encoded", field)
    return s


def clean_list(values, field: str, stats: dict | None = None) -> list[str]:
    out = set()
    for v in values or []:
        c = clean_str(v, field, stats)
        if c is not None:
            out.add(c)
    return sorted(out)


def normalize_record(level: str, raw: dict, stats: dict | None = None) -> dict:
    ids = raw.get("ids") or {}
    rec = {
        "level": level,
        "id": _id(raw["id"]),
        "display_name": clean_str(raw.get("display_name"), "display_name", stats),
        "description": clean_str(raw.get("description"), "description", stats),
        "alternatives": clean_list(raw.get("display_name_alternatives"), "alternatives", stats),
        "wikidata": clean_url(ids.get("wikidata"), "wikidata", stats),
        "wikipedia": clean_url(ids.get("wikipedia"), "wikipedia", stats),
        "siblings": sorted({_id(s) for s in (raw.get("siblings") or []) if _id(s)}),
    }
    if not rec["display_name"]:
        raise SystemExit(f"{level} {rec['id']} has no display_name after normalization")
    if level in ("field", "subfield", "topic"):
        rec["domain"] = _id(raw.get("domain"))
    if level in ("subfield", "topic"):
        rec["field"] = _id(raw.get("field"))
    if level == "topic":
        rec["subfield"] = _id(raw.get("subfield"))
        rec["keywords"] = clean_list(raw.get("keywords"), "keywords", stats)
    return {k: v for k, v in rec.items() if k == "siblings" or v not in (None, "", [])}


def fetch_api(cfg: dict, stats: dict, sleep=time.sleep) -> tuple[list[dict], dict]:
    limiter = RateLimiter(cfg["rate"], sleep=sleep)
    records, meta_counts, remaining = [], {}, None
    for level in LEVELS:
        cursor, n, count = "*", 0, None
        while cursor:
            data, headers = get_json(page_url(level, cursor), cfg["api_key"], limiter, sleep=sleep)
            meta = data.get("meta", {})
            if count is None:
                count = meta.get("count")
            results = data.get("results", [])
            records.extend(normalize_record(level, raw, stats) for raw in results)
            n += len(results)
            remaining = headers.get("X-RateLimit-Remaining", remaining)
            cursor = meta.get("next_cursor") if results else None
        meta_counts[level] = count
        print(f"{level}: {n} records (meta.count={count})", file=sys.stderr)
    if remaining is not None:
        print(f"daily budget remaining: {remaining}", file=sys.stderr)
    return records, meta_counts


def read_jsonl(path: Path, stats: dict) -> tuple[list[dict], dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            records.append(normalize_record(raw.pop("level"), raw, stats))
    counts = Counter(r["level"] for r in records)
    return records, {lv: counts[lv] for lv in LEVELS}


def sibling_stats(records: list[dict]) -> tuple[dict, dict]:
    """Pairs as listed, and listed siblings that are not entities of the same level."""
    ids = {lv: {r["id"] for r in records if r["level"] == lv} for lv in LEVELS}
    pairs, dangling = Counter(), Counter()
    for r in records:
        for s in r["siblings"]:
            if s in ids[r["level"]]:
                pairs[r["level"]] += 1
            else:
                dangling[r["level"]] += 1
    return {lv: pairs[lv] for lv in LEVELS}, {lv: dangling[lv] for lv in LEVELS}


def write_outputs(records: list[dict], meta_counts: dict, source: str,
                  out_dir: Path = OUT_DIR, fetched_at: str | None = None,
                  stats: dict | None = None) -> dict:
    seen = set()
    for r in records:
        key = (r["level"], r["id"])
        if key in seen:
            raise SystemExit(f"duplicate record {key}")
        seen.add(key)
    records = sorted(records, key=lambda r: (LEVELS.index(r["level"]), int(r["id"].lstrip("T"))))
    out_dir.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in records)
    (out_dir / "openalex-taxonomy.jsonl").write_bytes(body.encode("utf-8"))
    counts = Counter(r["level"] for r in records)
    counts = {lv: counts[lv] for lv in LEVELS}
    pairs, dangling = sibling_stats(records)
    manifest = {
        "source": source,
        "fetched_at": fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_base": API_BASE,
        "counts": counts,
        "api_meta_counts": meta_counts,
        "jsonl_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "sibling_pairs": pairs,
        "dangling_siblings": dangling,
        "normalization": {k: dict(sorted(v.items())) for k, v in (stats or new_stats()).items()},
    }
    dev = {lv: [PUBLISHED[lv], counts[lv]] for lv in LEVELS if counts[lv] != PUBLISHED[lv]}
    if dev:
        manifest["count_deviations"] = dev
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["api", "jsonl"], required=True)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--input", type=Path)
    a = ap.parse_args(argv)
    stats = new_stats()
    if a.source == "api":
        records, meta = fetch_api(load_config(a.config), stats)
    else:
        if not a.input:
            raise SystemExit("--source jsonl needs --input")
        records, meta = read_jsonl(a.input, stats)
    m = write_outputs(records, meta, a.source, stats=stats)
    print(json.dumps(m, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
