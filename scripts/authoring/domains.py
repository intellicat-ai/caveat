#!/usr/bin/env python3
"""Stage 5: candidate domains and contamination probes.

Usage:
    domains.py rank <slug> TERM [TERM ...] [--top N]   topics of works matching any term, by lift
    domains.py probe <slug> TOPIC                       random and top-cited samples of a topic
    domains.py summarize <slug> TOPIC                   n, hits and a Wilson 95% interval per stratum

rank prints each topic's share of the matching works, its lift over the
corpus at large, and its OpenAlex label and keywords, which the drafter needs
for the dedicated-domain test (docs: mappings/README.md). The statistics
inform that judgment; they are not the criterion.

probe writes work/<slug>/domain-probes/<topic>.{random,topcited}.jsonl, 50
works each, with label: null. The drafter labels each work against the draft
definition and a reviewer confirms. Per-paper labels never leave work/; only
the summarize aggregates go into mappings/openalex/mode-domains.csv.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openalex  # noqa: E402
from net import ROOT, Client  # noqa: E402
from stats import lift, wilson_text  # noqa: E402

PROBE_N, PROBE_SEED = 50, 1


def any_phrase(terms: list[str]) -> str:
    phrases = " OR ".join('"' + t.replace(",", " ").replace('"', " ").strip() + '"' for t in terms)
    return f"title_and_abstract.search:({phrases})"


def rank(client: Client, terms: list[str], top: int) -> list[dict]:
    filt = any_phrase(terms)
    groups = openalex.group_by(client, filt, "primary_topic.id")
    k_total = sum(g["count"] for g in groups)
    corpus = client.json(f"{openalex.API}/works", params={"per-page": 1, "select": "id"},
                         headers=openalex._headers(client))["meta"]["count"]
    rows = []
    for g in groups[:top]:
        if not g["key"] or g["key"] == "unknown":
            continue
        t = openalex.topic(client, g["key"]) or {}
        rows.append({
            "topic": f"caveatoa:{openalex.short_id(g['key'])}",
            "label": t.get("display_name"),
            "keywords": [k["display_name"] for k in t.get("keywords", [])],
            "subfield": (t.get("subfield") or {}).get("display_name"),
            "matching": g["count"],
            "share_of_seed": round(g["count"] / k_total, 3) if k_total else 0,
            "lift": round(lift(g["count"], k_total, t.get("works_count", 0), corpus), 1),
        })
    rows.sort(key=lambda r: -r["lift"])
    return [{"query": filt, "seed_n": k_total, "date": datetime.date.today().isoformat()}] + rows


def probe(client: Client, slug: str, topic: str) -> list[str]:
    tid = openalex.short_id(topic.split(":")[-1])
    d = ROOT / "work" / slug / "domain-probes"
    d.mkdir(parents=True, exist_ok=True)
    filt = f"primary_topic.id:{tid}"
    fields = "id,title,publication_year,cited_by_count"
    written = []
    for stratum, works in (("random", openalex.sample(client, filt, PROBE_N, PROBE_SEED, fields)),
                           ("topcited", openalex.top_cited(client, filt, PROBE_N, fields))):
        path = d / f"{tid}.{stratum}.jsonl"
        with open(path, "w") as fh:
            fh.write(json.dumps({"topic": tid, "stratum": stratum, "query": filt, "seed": PROBE_SEED,
                                 "date": datetime.date.today().isoformat()}) + "\n")
            for w in works:
                fh.write(json.dumps({"id": openalex.short_id(w["id"]), "title": w["title"],
                                     "year": w["publication_year"], "cited_by_count": w["cited_by_count"],
                                     "label": None}, ensure_ascii=False) + "\n")
        written.append(str(path.relative_to(ROOT)))
    return written


def summarize(slug: str, topic: str) -> dict:
    tid = openalex.short_id(topic.split(":")[-1])
    out = {"topic": f"caveatoa:{tid}"}
    for stratum in ("random", "topcited"):
        path = ROOT / "work" / slug / "domain-probes" / f"{tid}.{stratum}.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()[1:] if l.strip()]
        if any(r["label"] is None for r in rows):
            raise SystemExit(f"{path.name}: unlabelled works remain")
        k, n = sum(bool(r["label"]) for r in rows), len(rows)
        out |= {f"probe_{stratum}_n": n, f"probe_{stratum}_hits": k, f"probe_{stratum}_ci": wilson_text(k, n)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank"); r.add_argument("slug"); r.add_argument("terms", nargs="+")
    r.add_argument("--top", type=int, default=15)
    p = sub.add_parser("probe"); p.add_argument("slug"); p.add_argument("topic")
    s = sub.add_parser("summarize"); s.add_argument("slug"); s.add_argument("topic")
    a = ap.parse_args(argv)
    if a.cmd == "rank":
        rows = rank(Client(), a.terms, a.top)
    elif a.cmd == "probe":
        rows = [{"written": f} for f in probe(Client(), a.slug, a.topic)]
    else:
        rows = [summarize(a.slug, a.topic)]
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
