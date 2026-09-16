#!/usr/bin/env python3
"""Validate CAVEAT assessment payloads (profile caveat-assessment/1).

Usage:
    python scripts/check_assessment.py FILE.json [...] [--taxonomy TTL]

Library use (call this before storing a payload):
    from check_assessment import load_graph, check
    g = load_graph()                 # once
    errors = check(payload, g)       # [] means valid

Structure is checked against vocabularies/profiles/assessment-1.schema.json.
Semantics checked here:
  * every caveat: CURIE resolves to the right kind of term
  * the applied link belongs to the observed marker
  * a fixed link's mode equals the assessed mode or is a subclass of it
  * a stated-reason link carries stated_mode, and that mode equals the
    assessed mode or is a subclass of it; fixed links carry no stated_mode
  * graded links carry intensity; the strength equals the band of the
    intensity; otherwise the strength equals the link's strength
  * caveat_version is not newer than the ontology
  * claimed_topic exists in the OpenAlex taxonomy, if one is supplied
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
CAVEATOA = Namespace("https://w3id.org/intellicat/caveat/modules/openalex#")
ROOT_ONTOLOGY = URIRef("https://w3id.org/intellicat/caveat")
REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
SCHEMA = REPO_ROOT / "vocabularies" / "profiles" / "assessment-1.schema.json"


def load_graph(ontology_dir: Path = ONTOLOGY_DIR) -> Graph:
    g = Graph()
    for f in sorted(Path(ontology_dir).rglob("*.ttl")):
        g.parse(f, format="turtle")
    return g


def _iri(curie: str) -> URIRef:
    prefix, _, local = curie.partition(":")
    return {"caveat": CAVEAT, "caveatoa": CAVEATOA}[prefix][local]


def _under(g: Graph, node: URIRef, root: URIRef) -> bool:
    return root in set(g.transitive_objects(node, RDFS.subClassOf))


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in v.split("-")[0].split(".")[:3])


def band(g: Graph, intensity: float) -> URIRef:
    ranked = []
    for s in g.subjects(RDF.type, CAVEAT.EvidenceStrength):
        lb = g.value(s, CAVEAT.intensityLowerBound)
        if lb is not None:
            ranked.append((Decimal(str(lb)), s))
    x = Decimal(str(intensity))
    return max((b for b in ranked if b[0] <= x), key=lambda b: b[0])[1]


def _schema_errors(obj) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is not installed; structure not checked"]
    if not hasattr(jsonschema, "Draft202012Validator"):
        from importlib.metadata import version
        return [f"jsonschema >= 4.18 is required (found {version('jsonschema')})"]
    schema = json.loads(SCHEMA.read_text())
    v = jsonschema.Draft202012Validator(schema)
    return [f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path))]


def check(obj: dict, g: Graph, taxonomy: Graph | None = None) -> list[str]:
    errs = _schema_errors(obj)
    if errs:
        return errs

    onto_v = str(g.value(ROOT_ONTOLOGY, OWL.versionInfo) or "0.0.0")
    if _vt(obj["caveat_version"]) > _vt(onto_v):
        errs.append(f"caveat_version {obj['caveat_version']} is newer than ontology {onto_v}")

    if "claimed_topic" in obj and taxonomy is not None:
        if (_iri(obj["claimed_topic"]), RDF.type, CAVEAT.OpenAlexTopic) not in taxonomy:
            errs.append(f"claimed_topic {obj['claimed_topic']} is not an OpenAlex topic")

    relations = set(g.subjects(RDF.type, CAVEAT.TopicRelation))
    graded = CAVEAT.GradedEvidence

    for i, a in enumerate(obj["assessments"]):
        where = f"assessments[{i}]"
        mode = _iri(a["mode"])
        if not (mode == CAVEAT.UnreliabilityMode or _under(g, mode, CAVEAT.UnreliabilityMode)):
            errs.append(f"{where}.mode {a['mode']} is not an unreliability mode")
            continue
        for j, o in enumerate(a["observations"]):
            w = f"{where}.observations[{j}]"
            marker = _iri(o["marker"])
            if not _under(g, marker, CAVEAT.DetectionMarker):
                errs.append(f"{w}.marker {o['marker']} is not a detection marker")
                continue
            link = _iri(o["link"])
            stated = (link, RDF.type, CAVEAT.StatedReasonEvidenceLink) in g
            if not stated and (link, RDF.type, CAVEAT.EvidenceLink) not in g:
                errs.append(f"{w}.link {o['link']} is not an evidence link")
                continue
            if g.value(link, CAVEAT.linkMarker) != marker:
                errs.append(f"{w}.link {o['link']} does not belong to marker {o['marker']}")
            if stated:
                if "stated_mode" not in o:
                    errs.append(f"{w}: stated-reason link requires stated_mode")
                else:
                    sm = _iri(o["stated_mode"])
                    if not _under(g, sm, CAVEAT.UnreliabilityMode):
                        errs.append(f"{w}.stated_mode {o['stated_mode']} is not an unreliability mode")
                    elif not (sm == mode or _under(g, sm, mode)):
                        errs.append(f"{w}.stated_mode {o['stated_mode']} does not support mode {a['mode']}")
            else:
                if "stated_mode" in o:
                    errs.append(f"{w}: stated_mode is only allowed with a stated-reason link")
                lm = g.value(link, CAVEAT.linkMode)
                if not (lm == mode or _under(g, lm, mode)):
                    errs.append(f"{w}.link mode {lm} does not support mode {a['mode']}")
            ls = g.value(link, CAVEAT.evidenceStrength)
            if ls == graded:
                if "intensity" not in o:
                    errs.append(f"{w}: graded link requires intensity")
                    continue
                expected = band(g, o["intensity"])
            else:
                expected = ls
            if "strength" in o:
                got = _iri(o["strength"])
                if got == graded:
                    errs.append(f"{w}.strength must be a ranked strength, not GradedEvidence")
                elif got != expected:
                    errs.append(f"{w}.strength {o['strength']} != expected {expected.split('#')[1]}")
            if "topic_relation" in o and _iri(o["topic_relation"]) not in relations:
                errs.append(f"{w}.topic_relation {o['topic_relation']} is not a topic relation")
            for k in o.get("topic_relation_counts", {}):
                if _iri(k) not in relations:
                    errs.append(f"{w}.topic_relation_counts key {k} is not a topic relation")
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--ontology", default=str(ONTOLOGY_DIR))
    ap.add_argument("--taxonomy")
    a = ap.parse_args(argv)
    g = load_graph(Path(a.ontology))
    tax = Graph().parse(a.taxonomy, format="turtle") if a.taxonomy else None
    bad = 0
    for f in a.files:
        errs = check(json.loads(Path(f).read_text()), g, tax)
        for e in errs:
            print(f"{f}: {e}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
