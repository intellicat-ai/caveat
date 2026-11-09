#!/usr/bin/env python3
"""Stages 3 and 4: candidate terms, their OpenAlex counts, and precision probes.

Usage:
    terms.py extract <slug> [--top N]          candidates from work/<slug>/sources/*.txt
    terms.py counts <slug> TERM [TERM ...]      OpenAlex exact-phrase counts (title+abstract, title)
    terms.py probe <slug> TERM [TERM ...] [--context WORDS]
                                                sample 20 titles per term for labelling; with
                                                --context, only works whose title or abstract
                                                also has one of WORDS (as context_required)
    terms.py precision <slug>                   precision per labelled term, and the level it supports

extract ranks noun phrases by how many exemplar texts contain them, then by
frequency, and drops phrases found in only one text. Topic keywords and
rejection-polarity terms are added by the drafter, not here.

probe writes work/<slug>/probes/<term>.jsonl with label: null on every line.
The drafter sets each label to true (the title belongs to the draft mode) or
false, and precision reads them back. Probe labels are corpus data: they stay
in work/ and never go into CAVEAT.
"""
import argparse
import collections
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openalex  # noqa: E402
from net import ROOT, Client  # noqa: E402
from stats import level_for, wilson_text  # noqa: E402

PROBE_N, PROBE_SEED = 20, 1
# Identifier labels that reference lists and web pages scatter through texts.
STOP_TERMS = {"pmid", "pmc", "pmcid", "s2cid", "issn", "isbn", "doi", "arxiv", "bibcode", "oclc", "et al"}
STOP_HEADS = {"study", "studies", "paper", "result", "results", "effect", "effects", "group", "groups",
              "patient", "patients", "method", "methods", "analysis", "data", "use", "level", "levels"}


def term_key(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def load_nlp():
    import spacy
    for model in ("en_core_sci_sm", "en_core_web_sm"):
        try:
            return spacy.load(model, disable=["ner"]), model
        except OSError:
            continue
    raise SystemExit("no spaCy model: python -m spacy download en_core_web_sm")


def phrases(doc) -> list[str]:
    out = []
    for chunk in doc.noun_chunks:
        toks = [t for t in chunk if not (t.is_stop or t.is_punct or t.like_num or t.pos_ == "DET")]
        if not toks or toks[-1].lemma_.lower() in STOP_HEADS or len(toks) > 5:
            continue
        text = " ".join(t.text.lower() for t in toks)
        if len(text) > 3 and re.search(r"[a-z]", text) and text not in STOP_TERMS:
            out.append(text)
    return out


def extract(slug: str, top: int) -> list[dict]:
    nlp, model = load_nlp()
    nlp.max_length = 3_000_000
    docfreq, freq = collections.Counter(), collections.Counter()
    texts = sorted((ROOT / "work" / slug / "sources").glob("*.txt"))
    for f in texts:
        ps = phrases(nlp(f.read_text()))
        freq.update(ps)
        docfreq.update(set(ps))
    # Multi-word phrases first: single nouns are rarely diagnostic.
    ranked = sorted((p for p in docfreq if docfreq[p] > 1 or len(texts) == 1),
                    key=lambda p: (" " not in p, -docfreq[p], -freq[p], p))
    return [{"term": p, "texts": docfreq[p], "occurrences": freq[p], "model": model} for p in ranked[:top]]


def counts(client: Client, terms: list[str]) -> list[dict]:
    today = datetime.date.today().isoformat()
    out = []
    for t in terms:
        ta, ti = openalex.phrase_filter(t), openalex.phrase_filter(t, "title")
        out.append({"term": t, "title_and_abstract": openalex.count(client, ta),
                    "title": openalex.count(client, ti), "query": ta, "date": today})
    return out


def context_filter(words: list[str]) -> str:
    return "title_and_abstract.search:(" + " OR ".join(w.replace(",", " ") for w in words) + ")"


def probe(client: Client, slug: str, terms: list[str], context: list[str] | None = None) -> None:
    d = ROOT / "work" / slug / "probes"
    d.mkdir(parents=True, exist_ok=True)
    for t in terms:
        filt = openalex.phrase_filter(t) + ",language:en"
        if context:
            filt += "," + context_filter(context)
        works = openalex.sample(client, filt, PROBE_N, PROBE_SEED, fields="id,title,publication_year")
        name = term_key(t) + ("--" + term_key("-".join(context)) if context else "")
        with open(d / f"{name}.jsonl", "w") as fh:
            fh.write(json.dumps({"term": t, "context_required": " OR ".join(context) if context else None,
                                 "query": filt, "seed": PROBE_SEED,
                                 "date": datetime.date.today().isoformat()}) + "\n")
            for w in works:
                fh.write(json.dumps({"id": openalex.short_id(w["id"]), "title": w["title"],
                                     "year": w["publication_year"], "label": None}, ensure_ascii=False) + "\n")


def precision(slug: str) -> list[dict]:
    out = []
    for f in sorted((ROOT / "work" / slug / "probes").glob("*.jsonl")):
        lines = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        head, rows = lines[0], lines[1:]
        labelled = [r["label"] for r in rows if r["label"] is not None]
        if len(labelled) < len(rows):
            out.append({"term": head["term"], "status": f"{len(rows) - len(labelled)} of {len(rows)} unlabelled"})
            continue
        k, n = sum(bool(x) for x in labelled), len(labelled)
        p = k / n if n else 0.0
        out.append({"term": head["term"], "context_required": head.get("context_required"), "hits": k, "n": n,
                    "precision": round(p, 2), "ci": wilson_text(k, n), "level": level_for(p)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract"); e.add_argument("slug"); e.add_argument("--top", type=int, default=60)
    c = sub.add_parser("counts"); c.add_argument("slug"); c.add_argument("terms", nargs="+")
    p = sub.add_parser("probe"); p.add_argument("slug"); p.add_argument("terms", nargs="+")
    p.add_argument("--context", nargs="+", help="context words; the term counts only with one of them")
    r = sub.add_parser("precision"); r.add_argument("slug")
    a = ap.parse_args(argv)
    if a.cmd == "extract":
        rows = extract(a.slug, a.top)
    elif a.cmd == "counts":
        rows = counts(Client(), a.terms)
    elif a.cmd == "probe":
        probe(Client(), a.slug, a.terms, a.context)
        rows = [{"probed": t, "context": a.context} for t in a.terms]
    else:
        rows = precision(a.slug)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
