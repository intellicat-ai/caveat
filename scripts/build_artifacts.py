#!/usr/bin/env python3
"""Build the published CAVEAT release artifacts from src/ontology.

Usage:
    python scripts/build_artifacts.py <output-dir>

Writes, relative to <output-dir>:
    caveat.ttl        root ontology (copy; metadata + owl:imports only)
    caveat-full.ttl   all modules and imports merged, Turtle
    caveat.owl        the same merged graph, RDF/XML
    modules/*.ttl     module sources
    imports/*.ttl     BFO/IAO excerpts

Single source of truth for what gets published. The Pages workflow calls
this; so does tests/test_release_artifacts.py. Neither reimplements it.
"""
import shutil
import sys
from pathlib import Path

from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"


def merged_graph() -> Graph:
    g = Graph()
    for ttl in sorted(ONTOLOGY_DIR.rglob("*.ttl")):
        g.parse(ttl, format="turtle")
    return g


def build(out_dir: Path) -> Graph:
    out_dir = Path(out_dir)
    (out_dir / "modules").mkdir(parents=True, exist_ok=True)
    (out_dir / "imports").mkdir(parents=True, exist_ok=True)

    shutil.copy2(ONTOLOGY_DIR / "caveat.ttl", out_dir / "caveat.ttl")
    for f in sorted((ONTOLOGY_DIR / "modules").glob("*.ttl")):
        shutil.copy2(f, out_dir / "modules" / f.name)
    for f in sorted((ONTOLOGY_DIR / "imports").glob("*.ttl")):
        shutil.copy2(f, out_dir / "imports" / f.name)

    g = merged_graph()
    g.serialize(destination=str(out_dir / "caveat-full.ttl"), format="turtle")
    g.serialize(destination=str(out_dir / "caveat.owl"), format="xml")
    return g


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    graph = build(Path(sys.argv[1]))
    print(f"built {len(graph)} triples into {sys.argv[1]}")
