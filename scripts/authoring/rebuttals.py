#!/usr/bin/env python3
"""Stage 7: verify rebuttal sources.

Usage:
    python scripts/authoring/rebuttals.py SOURCE [SOURCE ...] [--archive]

A SOURCE is a DOI or an http(s) URL. For a DOI, Crossref gives the title,
year, venue and any retraction, withdrawal or expression of concern;
OpenAlex gives the work id and its retraction flag. For a URL, the page must
answer, and the Wayback Machine is asked for an existing snapshot; with
--archive, a new snapshot is requested when none exists (an outward action:
use it only when the proposal needs the archive).

Prints one JSON object per source with the fields of a proposal rebuttal
entry. kind and venueType are left null: classifying what a source contains
is the drafter's judgment, recorded in the proposal and checked in review.
A source that does not resolve is reported as unresolved and must not be used.
"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openalex  # noqa: E402
from net import Client  # noqa: E402

NOTICE_TYPES = {"retraction", "withdrawal", "removal", "expression_of_concern", "correction"}


def verify_doi(client: Client, doi: str) -> dict:
    doi = doi.removeprefix("https://doi.org/").strip()
    params = {"mailto": client.config["mailto"]} if client.config.get("mailto") else None
    d = client.json(f"https://api.crossref.org/works/{doi}", params=params)
    if d is None:
        return {"ref": doi, "status": "unresolved"}
    m = d["message"]
    notices = sorted({u.get("type") for u in m.get("updated-by", [])} & NOTICE_TYPES)
    w = openalex.work(client, doi)
    retracted = bool((w or {}).get("is_retracted")) or any(n in ("retraction", "withdrawal", "removal") for n in notices)
    return {
        "status": "ok",
        "source": f"https://doi.org/{m['DOI']}",
        "doi": m["DOI"],
        "is_retracted": retracted,
        "notices": notices,
        "openalex_id": openalex.short_id((w or {}).get("id")),
        "title": (m.get("title") or [""])[0],
        "year": ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0],
        "container": (m.get("container-title") or [""])[0],
        "kind": None,
        "venueType": None,
    }


def wayback(url: str, archive: bool, live: Client) -> tuple[str | None, str]:
    """(snapshot URL or None, what happened). A failed lookup is reported, never fatal."""
    r = live.get("https://archive.org/wayback/available", params={"url": url})
    if r.status_code != 200:
        return None, f"archive_lookup_http_{r.status_code}"
    snap = (r.json().get("archived_snapshots") or {}).get("closest") or {}
    if snap.get("available"):
        return snap["url"].replace("http://", "https://", 1), "archived"
    if not archive:
        return None, "not_archived"
    r = live.get(f"https://web.archive.org/save/{url}")
    if r.status_code in (200, 302) and "/web/" in r.url:
        return r.url, "archived_now"
    return None, f"archive_save_http_{r.status_code}"


def verify_url(client: Client, url: str, archive: bool, live: Client) -> dict:
    r = live.get(url, allow_redirects=True)
    if r.status_code != 200:
        return {"ref": url, "status": f"http_{r.status_code}"}
    title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
    archived, how = wayback(url, archive, live)
    return {
        "status": "ok" if archived else how,
        "source": url,
        "archivedAt": archived,
        "title": html.unescape(" ".join(title.group(1).split())) if title else None,
        "year": None,
        "kind": None,
        "venueType": None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--archive", action="store_true", help="request a Wayback snapshot when none exists")
    a = ap.parse_args(argv)
    client, live = Client(), Client(cache=False)
    today = datetime.date.today().isoformat()
    for s in a.sources:
        if re.match(r"^(10\.|https://doi\.org/)", s):
            rec = verify_doi(client, s)
        elif re.match(r"^https?://", s):
            rec = verify_url(client, s, a.archive, live)
        else:
            rec = {"ref": s, "status": "unrecognized"}
        rec["retrieved"] = today
        print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
