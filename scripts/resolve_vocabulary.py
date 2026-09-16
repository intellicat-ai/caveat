#!/usr/bin/env python3
"""Resolve the full inherited vocabulary for a given CAVEAT unreliability mode.

Usage:
    python resolve_vocabulary.py caveat:BiofieldEnergyHealing

Traverses the rdfs:subClassOf chain from the given mode to the root,
collects all referenced lexicon files, loads and merges them, and outputs
the combined vocabulary as JSON.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

try:
    from rdflib import Graph, Namespace, URIRef
    from rdflib.namespace import RDFS
except ImportError:
    sys.exit("rdflib required: pip install rdflib")

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
VOCAB_DIR = REPO_ROOT / "vocabularies"


def load_ontology() -> Graph:
    """Load all CAVEAT ontology modules into a single graph."""
    g = Graph()
    modules_dir = ONTOLOGY_DIR / "modules"
    for ttl_file in modules_dir.glob("*.ttl"):
        g.parse(ttl_file, format="turtle")
    return g


def get_ancestor_chain(g: Graph, mode_uri: URIRef) -> list[URIRef]:
    """Breadth-first over all CAVEAT parents. Nearest first; ties by IRI."""
    dist = {mode_uri: 0}
    frontier = [mode_uri]
    while frontier:
        nxt = set()
        for node in frontier:
            for p in g.objects(node, RDFS.subClassOf):
                if isinstance(p, URIRef) and str(p).startswith(str(CAVEAT)) and p not in dist:
                    dist[p] = dist[node] + 1
                    nxt.add(p)
        frontier = sorted(nxt, key=str)
    return sorted(dist, key=lambda u: (dist[u], str(u)))


def resolve_lexicon_files(g: Graph, mode_uri: URIRef) -> list[str]:
    """Ordered lexicon files, nearest ancestor first, each once."""
    files = []
    for ancestor in get_ancestor_chain(g, mode_uri):
        for lexicon in sorted(str(o) for o in g.objects(ancestor, CAVEAT.lexiconFile)):
            if lexicon not in files:
                files.append(lexicon)
    return files


def load_and_merge_lexicons(files: list[str]) -> dict:
    """Load YAML lexicon files and merge terms (child-first precedence)."""
    all_terms = {}
    # Process in reverse (root first) so children override
    for filepath in reversed(files):
        full_path = VOCAB_DIR / filepath
        if not full_path.exists():
            print(f"Warning: lexicon file not found: {full_path}", file=sys.stderr)
            continue
        with open(full_path) as f:
            data = yaml.safe_load(f)
        for term_entry in data.get("terms", []):
            term = term_entry["term"]
            all_terms[term] = term_entry
    return {
        "mode": str(files[0]) if files else None,
        "lexicon_files": files,
        "term_count": len(all_terms),
        "terms": list(all_terms.values()),
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve CAVEAT vocabulary inheritance")
    parser.add_argument("mode", help="CAVEAT mode URI, e.g. caveat:BiofieldEnergyHealing")
    args = parser.parse_args()

    mode_local = args.mode.replace("caveat:", "")
    mode_uri = CAVEAT[mode_local]

    g = load_ontology()
    files = resolve_lexicon_files(g, mode_uri)

    if not files:
        print(f"No lexicon files found for {args.mode}", file=sys.stderr)
        sys.exit(1)

    merged = load_and_merge_lexicons(files)
    print(json.dumps(merged, indent=2))


if __name__ == "__main__":
    main()
