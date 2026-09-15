#!/usr/bin/env python3
"""Build or check merged CAVEAT release artifacts for publication.

Generates:
- docs/caveat.ttl (merged Turtle artifact)
- docs/caveat.owl (merged RDF/XML artifact)

Usage:
    python scripts/build_release.py          # Generate artifacts
    python scripts/build_release.py --check  # Verify artifacts match source
"""

import argparse
import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
DOCS_DIR = REPO_ROOT / "docs"

ROOT_ONTOLOGY = URIRef("https://w3id.org/intellicat/caveat")
CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
OBO = Namespace("http://purl.obolibrary.org/obo/")

HEADER_COMMENT = """# CAVEAT Ontology - Merged Release Artifact
# Generated file - do not edit.
# Source: src/ontology/
# Regenerate with: python scripts/build_release.py

"""


def build_graph(ontology_dir: Path | None = None) -> Graph:
    """Load all ontology modules, strip internal imports and module declarations, and return merged graph."""
    if ontology_dir is None:
        ontology_dir = ONTOLOGY_DIR

    g = Graph()
    for ttl_file in sorted(ontology_dir.rglob("*.ttl")):
        g.parse(ttl_file, format="turtle")

    # 1. Delete all owl:imports triples
    g.remove((None, OWL.imports, None))

    # 2. Delete module/excerpt owl:Ontology declarations and any triples whose subject is one of them
    other_ontologies = {
        s for s in g.subjects(RDF.type, OWL.Ontology)
        if s != ROOT_ONTOLOGY
    }
    for onto in other_ontologies:
        g.remove((onto, None, None))

    # 3. Bind prefixes cleanly
    g.bind("caveat", CAVEAT, override=True)
    g.bind("obo", OBO, override=True)
    g.bind("owl", OWL, override=True)
    g.bind("rdf", RDF, override=True)
    g.bind("rdfs", RDFS, override=True)
    g.bind("xsd", XSD, override=True)
    g.bind("dcterms", DCTERMS, override=True)
    g.bind("skos", SKOS, override=True)

    return g


def write_release(docs_dir: Path | None = None) -> None:
    """Generate docs/caveat.ttl and docs/caveat.owl."""
    if docs_dir is None:
        docs_dir = DOCS_DIR

    docs_dir.mkdir(parents=True, exist_ok=True)
    g = build_graph()

    ttl_path = docs_dir / "caveat.ttl"
    owl_path = docs_dir / "caveat.owl"

    ttl_content = g.serialize(format="turtle")
    ttl_path.write_text(HEADER_COMMENT + ttl_content, encoding="utf-8")
    print(f"Wrote {ttl_path} ({len(g)} triples)")

    owl_content = g.serialize(format="xml")
    owl_path.write_text(owl_content, encoding="utf-8")
    print(f"Wrote {owl_path} ({len(g)} triples)")


def check_release(docs_dir: Path | None = None) -> bool:
    """Verify that release artifacts exist, parse, and are isomorphic to the built graph."""
    if docs_dir is None:
        docs_dir = DOCS_DIR

    ttl_path = docs_dir / "caveat.ttl"
    owl_path = docs_dir / "caveat.owl"

    if not ttl_path.exists():
        print(f"Error: {ttl_path} does not exist.", file=sys.stderr)
        return False
    if not owl_path.exists():
        print(f"Error: {owl_path} does not exist.", file=sys.stderr)
        return False

    built = build_graph()

    ttl_graph = Graph()
    try:
        ttl_graph.parse(ttl_path, format="turtle")
    except Exception as e:
        print(f"Error parsing {ttl_path}: {e}", file=sys.stderr)
        return False

    owl_graph = Graph()
    try:
        owl_graph.parse(owl_path, format="xml")
    except Exception as e:
        print(f"Error parsing {owl_path}: {e}", file=sys.stderr)
        return False

    if not isomorphic(built, ttl_graph):
        print(f"Error: {ttl_path} is not isomorphic to built graph.", file=sys.stderr)
        return False

    if not isomorphic(built, owl_graph):
        print(f"Error: {owl_path} is not isomorphic to built graph.", file=sys.stderr)
        return False

    print(f"Check passed: {ttl_path.name} and {owl_path.name} are up to date and isomorphic ({len(built)} triples).")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or check CAVEAT release artifacts.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that release artifacts are isomorphic to source ontology without modifying files.",
    )
    args = parser.parse_args()

    if args.check:
        if not check_release():
            sys.exit(1)
        sys.exit(0)
    else:
        write_release()


if __name__ == "__main__":
    main()
