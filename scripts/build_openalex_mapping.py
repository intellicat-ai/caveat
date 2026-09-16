#!/usr/bin/env python3
"""Build the OpenAlex SKOS mapping from the normalized jsonl.

Usage:
    python scripts/build_openalex_mapping.py          # write Turtle
    python scripts/build_openalex_mapping.py --check  # exit 1 if stale

Reads  mappings/openalex/openalex-taxonomy.jsonl and manifest.json
Writes mappings/openalex/openalex.ttl and openalex-siblings.ttl

Output is byte-deterministic: this script writes Turtle itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdflib import Literal, URIRef

REPO_ROOT = Path(__file__).resolve().parent.parent
DIR = REPO_ROOT / "mappings" / "openalex"
LEVELS = ["domain", "field", "subfield", "topic"]
CLASS = {"domain": "caveat:OpenAlexDomain", "field": "caveat:OpenAlexField",
         "subfield": "caveat:OpenAlexSubfield", "topic": "caveat:OpenAlexTopic"}
LOCAL = {"domain": "domain_{}", "field": "field_{}", "subfield": "subfield_{}", "topic": "{}"}
OA_IRI = {"domain": "https://openalex.org/domains/{}", "field": "https://openalex.org/fields/{}",
          "subfield": "https://openalex.org/subfields/{}", "topic": "https://openalex.org/{}"}
PARENT = {"field": ("domain", "caveat:parentDomain"), "subfield": ("field", "caveat:parentField"),
          "topic": ("subfield", "caveat:parentSubfield")}
SIBLING = {"domain": "caveat:siblingDomain", "field": "caveat:siblingField",
           "subfield": "caveat:siblingSubfield", "topic": "caveat:siblingTopic"}
ONT = "https://w3id.org/intellicat/caveat/modules/openalex"
SIBLINGS_ONT = "https://w3id.org/intellicat/caveat/modules/openalex-siblings"
PREFIXES = """@prefix caveat:   <https://w3id.org/intellicat/caveat#> .
@prefix caveatoa: <https://w3id.org/intellicat/caveat/modules/openalex#> .
@prefix dcterms:  <http://purl.org/dc/terms/> .
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos:     <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
"""


def node(level: str, i: str) -> str:
    return "caveatoa:" + LOCAL[level].format(i)


def lit(s: str, lang: str | None = "en") -> str:
    return Literal(s, lang=lang).n3()


IRI_UNSAFE = set(' "<>{}|\\^`') | {chr(c) for c in range(0x20)} | {chr(0x7f)}


def iri(s: str) -> str:
    if not s.lower().startswith(("http://", "https://")) or any(ch in IRI_UNSAFE for ch in s):
        raise SystemExit(f"refusing to write invalid IRI {s!r}; re-run the fetcher")
    return f"<{s}>"


def block(subject: str, pairs: list[tuple[str, list[str]]]) -> str:
    pairs = [(p, sorted(set(o))) for p, o in pairs if o]
    lines = [subject]
    for k, (p, objs) in enumerate(pairs):
        end = " ." if k == len(pairs) - 1 else " ;"
        lines.append(f"    {p} {', '.join(objs)}{end}")
    return "\n".join(lines) + "\n"


def load():
    records = [json.loads(l) for l in (DIR / "openalex-taxonomy.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((DIR / "manifest.json").read_text())
    return records, manifest


def render(records: list[dict], manifest: dict) -> tuple[str, str]:
    domains = [r for r in records if r["level"] == "domain"]
    out = [PREFIXES]
    out.append(block(f"<{ONT}>", [
        ("a", ["owl:Ontology"]),
        ("owl:imports", ["<https://w3id.org/intellicat/caveat>"]),
        ("caveat:openAlexSnapshotDate", [f'"{manifest["fetched_at"][:10]}"^^xsd:date']),
        ("dcterms:source", ["<https://api.openalex.org/>"]),
        ("dcterms:license", ["<https://creativecommons.org/publicdomain/zero/1.0/>"]),
        ("rdfs:comment", [lit("OpenAlex domains, fields, subfields and topics as SKOS concepts. "
                              "Names, descriptions and keywords are OpenAlex's own; OpenAlex "
                              "generates topic names and descriptions with a language model.")]),
    ]))
    out.append(block("caveatoa:scheme", [
        ("a", ["skos:ConceptScheme"]),
        ("skos:prefLabel", [lit("OpenAlex topic hierarchy")]),
        ("skos:hasTopConcept", [node("domain", d["id"]) for d in domains]),
    ]))
    for r in records:
        lv, i = r["level"], r["id"]
        pairs = [
            ("a", [CLASS[lv], "skos:Concept"]),
            ("skos:inScheme", ["caveatoa:scheme"]),
            ("skos:prefLabel", [lit(r["display_name"])]),
            ("rdfs:label", [lit(r["display_name"])]),
            ("skos:notation", [lit(i, None)]),
            ("caveat:openAlexId", [lit(i, None)]),
            ("skos:exactMatch", [iri(OA_IRI[lv].format(i))]),
            ("skos:scopeNote", [lit(r["description"])] if "description" in r else []),
            ("skos:altLabel", [lit(a) for a in r.get("alternatives", [])]),
            ("caveat:openAlexKeyword", [lit(k) for k in r.get("keywords", [])]),
            ("skos:closeMatch", [iri(r["wikidata"])] if "wikidata" in r else []),
            ("rdfs:seeAlso", [iri(r["wikipedia"])] if "wikipedia" in r else []),
        ]
        if lv == "domain":
            pairs.append(("skos:topConceptOf", ["caveatoa:scheme"]))
        else:
            plv, prop = PARENT[lv]
            p = node(plv, r[plv])
            pairs += [(prop, [p]), ("skos:broader", [p])]
        out.append(block(node(lv, i), pairs))
    taxonomy = "\n".join(out)

    ids = {lv: {r["id"] for r in records if r["level"] == lv} for lv in LEVELS}
    sib = [PREFIXES]
    sib.append(block(f"<{SIBLINGS_ONT}>", [
        ("a", ["owl:Ontology"]),
        ("owl:imports", [f"<{ONT}>"]),
        ("rdfs:comment", [lit("Sibling relations as listed by OpenAlex, at every level, in the "
                              "direction listed. Listed siblings that are not entities of the same "
                              "level are omitted and counted in manifest.json.")]),
    ]))
    for r in records:
        known = [s for s in r["siblings"] if s in ids[r["level"]]]
        if known:
            sib.append(block(node(r["level"], r["id"]),
                             [(SIBLING[r["level"]], [node(r["level"], s) for s in known])]))
    return taxonomy, "\n".join(sib)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    taxonomy, siblings = render(*load())
    targets = {DIR / "openalex.ttl": taxonomy, DIR / "openalex-siblings.ttl": siblings}
    if a.check:
        stale = [p.name for p, text in targets.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for name in stale:
            print(f"stale: {name}", file=sys.stderr)
        return 1 if stale else 0
    for p, text in targets.items():
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
