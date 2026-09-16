#!/usr/bin/env python3
"""Validate CAVEAT ontology for basic consistency.

Checks:
1. All .ttl files under src/ontology/ parse without errors
2. Every CAVEAT class has an rdfs:label
3. Every UnreliabilityMode and DetectionMarker class has a caveat:definition
4. Every UnreliabilityMode subclass has a caveat:defaultSeverity (warning only)
5. Every evidence link has a marker and a strength; strengths appear only on links
6. Subclass hierarchy: no cycles, no orphans, no undeclared CAVEAT parents
7. caveat:lexiconFile and caveat:retractionAwareLexiconFile values point to
   files that exist under vocabularies/
8. Every lexicon file conforms to vocabularies/_schema.yaml (required and
   allowed top-level keys, enum values for classification, level and
   general_frequency)

Usage:
    python scripts/validate.py
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


ROOT_CLASSES = {
    "UnreliabilityMode", "DetectionMarker", "CorpusFamily", "RetractionRecord",
    "OpenAlexDomain", "OpenAlexField", "OpenAlexSubfield", "OpenAlexTopic",
    "EvidenceStrength",
}


def check_hierarchy(g: Graph) -> list[str]:
    out = []
    ns = str(CAVEAT)
    declared = {c for c in g.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef)}
    for c in sorted(declared, key=str):
        if not str(c).startswith(ns):
            continue
        parents = [p for p in g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef)]
        if not parents and str(c)[len(ns):] not in ROOT_CLASSES:
            out.append(f"Orphan class (no rdfs:subClassOf): {c}")
        for p in parents:
            if str(p).startswith(ns) and p not in declared:
                out.append(f"Undeclared CAVEAT parent {p} of {c}")
        if c in set(g.transitive_objects(c, RDFS.subClassOf)) - {c} or any(
            c in set(g.transitive_objects(p, RDFS.subClassOf)) for p in parents
        ):
            out.append(f"Subclass cycle through {c}")
    return out


def check_evidence_links(g: Graph):
    links = set(g.subjects(RDF.type, CAVEAT.EvidenceLink)) | set(
        g.subjects(RDF.type, CAVEAT.StatedReasonEvidenceLink))
    for n in links:
        if g.value(n, CAVEAT.linkMarker) is None or g.value(n, CAVEAT.evidenceStrength) is None:
            errors.append(f"Evidence link {n} lacks marker or strength")
    for s in g.subjects(CAVEAT.evidenceStrength, None):
        if s not in links:
            errors.append(f"caveat:evidenceStrength on non-link {s}")


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


def check_lexicon_schema():
    """Validate lexicon files against vocabularies/_schema.yaml."""
    import yaml
    schema_path = VOCAB_DIR / "_schema.yaml"
    if not schema_path.exists():
        errors.append(f"Schema not found: {schema_path}")
        return
    schema = yaml.safe_load(schema_path.read_text())
    props = schema.get("properties", {})
    allowed_top = set(props)
    required_top = set(schema.get("required", []))
    term_props = props.get("terms", {}).get("items", {}).get("properties", {})
    enums = {
        k: set(term_props.get(k, {}).get("enum", []))
        for k in ("classification", "level", "general_frequency")
    }
    meta = set(schema.get("x-classification-metadata", {}))
    for c in sorted(set(enums["classification"]) - meta):
        errors.append(
            f"_schema.yaml: '{c}' is in the classification enum but missing "
            f"from x-classification-metadata"
        )
    for c in sorted(meta - set(enums["classification"])):
        errors.append(
            f"_schema.yaml: '{c}' is in x-classification-metadata but not in "
            f"the classification enum"
        )
    for f in sorted(VOCAB_DIR.rglob("*.yaml")):
        if f.name == "_schema.yaml":
            continue
        data = yaml.safe_load(f.read_text())
        for k in sorted(required_top - set(data)):
            errors.append(f"{f.name}: missing required key '{k}'")
        for k in sorted(set(data) - allowed_top):
            errors.append(f"{f.name}: undeclared top-level key '{k}'")
        for t in data.get("terms", []):
            for field, allowed in enums.items():
                if field == "classification" or field in t:
                    v = t.get(field)
                    if v not in allowed:
                        errors.append(
                            f"{f.name}: term '{t.get('term')}' has {field} "
                            f"'{v}' not in schema enum"
                        )


def main():
    print("Loading CAVEAT ontology...", flush=True)
    g = load_all()
    print(f"Loaded {len(g)} triples from {ONTOLOGY_DIR}", flush=True)

    print("Checking labels...", flush=True)
    check_labels(g)

    print("Checking definitions and severity...", flush=True)
    check_definitions(g)

    print("Checking hierarchy...", flush=True)
    errors.extend(check_hierarchy(g))

    print("Checking evidence links...", flush=True)
    check_evidence_links(g)

    print("Checking lexicon file references...", flush=True)
    check_lexicon_files(g)

    print("Checking lexicon schema conformance...", flush=True)
    check_lexicon_schema()

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
