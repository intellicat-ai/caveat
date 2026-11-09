#!/usr/bin/env python3
"""Stage 3b: harvest typicallyExhibits candidates from sampled full texts.

Usage:
    harvest.py sample <slug> TERM [TERM ...] [--n 20]   open-access works matching the terms
    harvest.py summarize <slug>                         counts per co-occurring mode

sample picks open-access works matching any of the high-precision terms,
acquires their full texts (as acquire.py does) into work/<slug>/harvest/, and
writes work/<slug>/harvest/labels.jsonl with modes: [] per work. The drafter
lists, for each work read, the other CAVEAT modes and markers it shows.
summarize counts them; a mode is a candidate at >= 5 works and >= 25% of the
works read. The exemplars count too: add their keys to labels.jsonl.
Per-paper labels never leave work/; the proposal records k of n, the query
and the date.
"""
import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import acquire  # noqa: E402
import openalex  # noqa: E402
from domains import any_phrase  # noqa: E402
from net import ROOT, Client  # noqa: E402
from stats import typical_candidate  # noqa: E402

SEED = 1


def sample(client: Client, slug: str, terms: list[str], n: int) -> dict:
    base = ROOT / "work" / slug / "harvest"
    texts, meta = base / "sources", base / "meta"
    texts.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    filt = any_phrase(terms) + ",is_oa:true,language:en"
    got, tried = [], 0
    for w in openalex.sample(client, filt, n * 3, SEED):
        if len(got) >= n:
            break
        tried += 1
        rec = acquire.acquire_work(client, openalex.short_id(w["id"]), texts, meta)
        if rec.get("status") == "ok":
            got.append(rec)
    with open(base / "labels.jsonl", "w") as fh:
        fh.write(json.dumps({"query": filt, "seed": SEED, "date": datetime.date.today().isoformat()}) + "\n")
        for rec in got:
            fh.write(json.dumps({"key": rec["key"], "title": rec["title"], "modes": []}, ensure_ascii=False) + "\n")
    return {"query": filt, "acquired": len(got), "tried": tried}


def summarize(slug: str) -> list[dict]:
    path = ROOT / "work" / slug / "harvest" / "labels.jsonl"
    lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    head, rows = lines[0], lines[1:]
    n = len(rows)
    tally = collections.Counter(m for r in rows for m in set(r["modes"]))
    return [{"mode": m, "k": k, "n": n, "query": head["query"], "date": head["date"],
             "candidate": typical_candidate(k, n)} for m, k in tally.most_common()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("slug"); s.add_argument("terms", nargs="+")
    s.add_argument("--n", type=int, default=20)
    m = sub.add_parser("summarize"); m.add_argument("slug")
    a = ap.parse_args(argv)
    rows = [sample(Client(), a.slug, a.terms, a.n)] if a.cmd == "sample" else summarize(a.slug)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
