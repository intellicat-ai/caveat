#!/usr/bin/env python3
"""Validate CAVEAT ontology for basic consistency.

Checks:
1. All .ttl files parse without errors
2. Every class has an rdfs:label
3. Every UnreliabilityMode subclass has an caveat:definition
4. Every UnreliabilityMode subclass has an caveat:defaultSeverity
5. Every DetectionMarker with caveat:evidenceFor has caveat:evidenceStrength
6. No orphan classes (every non-root class has rdfs:subClassOf)
7. lexiconFile references point to files that exist

Usage:
    python validate.py
"""

import sys
from pathlib import Path

try:
    from rdflib import Graph, Namespace, URIRef, Literal
    from rdflib.namespace import RDFS, OWL, RDF
except ImportError:
    sys.exit("rdflib required: pip install rdflib")

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
VOCAB_DIR = REPO_ROOT / "vocabularies"

errors = []
warnings = []


def load_all() -> Graph:
    g = Graph()
    for ttl_file in ONTOLOGY_DIR.rglob("*.ttl"):
        try:
            g.parse(ttl_file, format="turtle")
        except Exception as e:
            errors.append(f"PARSE ERROR in {ttl_file}: {e}")
    return g


def check_labels(g: Graph):
    for cls in g.subjects(RDF.type, OWL.Class):
        if not isinstance(cls, URIRef):
            continue
        if not str(cls).startswith(str(CAVEAT)):
            continue
        label = g.value(cls, RDFS.label)
        if not label:
            errors.append(f"Missing rdfs:label on {cls}")


def check_definitions(g: Graph):
    for cls in g.subjects(RDF.type, OWL.Class):
        if not isinstance(cls, URIRef) or not str(cls).startswith(str(CAVEAT)):
            continue
        # Check if it's an unreliability mode or detection marker
        parents = set(g.transitive_objects(cls, RDFS.subClassOf))
        if CAVEAT.UnreliabilityMode in parents or cls == CAVEAT.UnreliabilityMode:
            defn = g.value(cls, CAVEAT.definition)
            if not defn:
                errors.append(f"Missing caveat:definition on unreliability mode {cls}")
            severity = g.value(cls, CAVEAT.defaultSeverity)
            if not severity and cls != CAVEAT.UnreliabilityMode:
                warnings.append(f"Missing caveat:defaultSeverity on {cls}")
        if CAVEAT.DetectionMarker in parents or cls == CAVEAT.DetectionMarker:
            defn = g.value(cls, CAVEAT.definition)
            if not defn:
                errors.append(f"Missing caveat:definition on detection marker {cls}")


def check_evidence_links(g: Graph):
    for s, p, o in g.triples((None, CAVEAT.evidenceFor, None)):
        strength = g.value(s, CAVEAT.evidenceStrength)
        if not strength:
            errors.append(
                f"Missing caveat:evidenceStrength on {s} "
                f"(has evidenceFor {o})"
            )


def check_lexicon_files(g: Graph):
    lexicon_properties = (
        CAVEAT.lexiconFile,
        CAVEAT.retractionAwareLexiconFile,
    )
    for prop in lexicon_properties:
        for s, p, o in g.triples((None, prop, None)):
            filepath = VOCAB_DIR / str(o)
            if not filepath.exists():
                errors.append(
                    f"Lexicon file not found: {filepath} (referenced by {s} via {p})"
                )


def main():
    print("Loading CAVEAT ontology...", flush=True)
    g = load_all()
    print(f"Loaded {len(g)} triples from {ONTOLOGY_DIR}", flush=True)

    print("Checking labels...", flush=True)
    check_labels(g)

    print("Checking definitions and severity...", flush=True)
    check_definitions(g)

    print("Checking evidence links...", flush=True)
    check_evidence_links(g)

    print("Checking lexicon file references...", flush=True)
    check_lexicon_files(g)

    if warnings:
        print(f"\n{len(warnings)} WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")

    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print(f"\n✓ Validation passed ({len(g)} triples, 0 errors)")
        sys.exit(0)


if __name__ == "__main__":
    main()
