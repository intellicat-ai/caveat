#!/usr/bin/env python3
"""Build the published CAVEAT release artifacts from src/ontology.

Usage:
    python scripts/build_artifacts.py <output-dir>

Writes, relative to <output-dir>:
    caveat.ttl        root ontology (copy; metadata + owl:imports only)
    caveat-full.ttl   all modules and imports merged, Turtle
    caveat.owl        the same merged graph, RDF/XML
    modes.csv         one row per unreliability mode (see modes_rows)
    modules/*.ttl     module sources, plus the OpenAlex taxonomy
                      (modules/openalex.ttl, modules/openalex-siblings.ttl)
                      when mappings/openalex/ holds it
    imports/*.ttl     BFO/IAO excerpts
    examples/         copy of examples/
    vocabularies/     copy of vocabularies/, including the reporting profile

Single source of truth for what gets published. The Pages workflow calls
this; so does tests/test_release_artifacts.py. Neither reimplements it.
"""
import csv
import re
import shutil
import sys
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDFS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_vocabulary import load_and_merge_lexicons, resolve_lexicon_files  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
OPENALEX = "https://w3id.org/intellicat/caveat/modules/openalex#"
MODES_COLUMNS = [
    "mode_curie", "parent_curies", "category_curies", "default_severity",
    "finding_code", "lexicon_terms_resolved", "dedicated_domain", "host_domains",
]


def merged_graph() -> Graph:
    g = Graph()
    for ttl in sorted(ONTOLOGY_DIR.rglob("*.ttl")):
        g.parse(ttl, format="turtle")
    return g


def finding_code(local: str) -> str:
    """The snake_case local name shown to users, e.g. cold_fusion_lenr."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", local)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def curie(iri) -> str:
    iri = str(iri)
    if iri.startswith(str(CAVEAT)):
        return "caveat:" + iri[len(str(CAVEAT)):]
    if iri.startswith(OPENALEX):
        return "caveatoa:" + iri[len(OPENALEX):]
    return iri


def modes_rows(g: Graph) -> list[dict]:
    """One row per subclass of caveat:UnreliabilityMode, sorted by CURIE.

    List cells are |-separated and sorted. category_curies holds every
    top-level category above the mode (the mode itself for a category);
    more than one is legal and is reported by build().
    """
    ns = str(CAVEAT)
    parents = {}
    for c, p in g.subject_objects(RDFS.subClassOf):
        if str(c).startswith(ns) and str(p).startswith(ns):
            parents.setdefault(c, set()).add(p)

    def categories(mode, seen=()):
        found = set()
        for p in parents.get(mode, ()):
            if p == CAVEAT.UnreliabilityMode:
                found.add(mode)
            elif p not in seen:
                found |= categories(p, seen + (mode,))
        return found

    rows = []
    for mode in sorted(parents, key=str):
        cats = categories(mode)
        if not cats:
            continue  # markers, documents and other non-mode classes
        files = resolve_lexicon_files(g, mode)
        terms = load_and_merge_lexicons(files)["term_count"] if files else 0
        severity = g.value(mode, CAVEAT.defaultSeverity)
        dedicated = sorted(curie(o) for o in g.objects(mode, CAVEAT.dedicatedDomain))
        rows.append({
            "mode_curie": curie(mode),
            "parent_curies": "|".join(sorted(curie(p) for p in parents[mode])),
            "category_curies": "|".join(sorted(curie(c) for c in cats)),
            "default_severity": "" if severity is None else str(severity),
            "finding_code": finding_code(str(mode)[len(ns):]),
            "lexicon_terms_resolved": terms,
            "dedicated_domain": "|".join(dedicated),
            "host_domains": "|".join(sorted(curie(o) for o in g.objects(mode, CAVEAT.hostDomain))),
        })
    return rows


def write_modes_csv(g: Graph, path: Path) -> list[dict]:
    rows = modes_rows(g)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MODES_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def build(out_dir: Path) -> Graph:
    out_dir = Path(out_dir)
    (out_dir / "modules").mkdir(parents=True, exist_ok=True)
    (out_dir / "imports").mkdir(parents=True, exist_ok=True)

    shutil.copy2(ONTOLOGY_DIR / "caveat.ttl", out_dir / "caveat.ttl")
    for f in sorted((ONTOLOGY_DIR / "modules").glob("*.ttl")):
        shutil.copy2(f, out_dir / "modules" / f.name)
    for f in sorted((ONTOLOGY_DIR / "imports").glob("*.ttl")):
        shutil.copy2(f, out_dir / "imports" / f.name)

    for name in ("openalex.ttl", "openalex-siblings.ttl"):
        src = REPO_ROOT / "mappings" / "openalex" / name
        if src.exists():
            shutil.copy2(src, out_dir / "modules" / name)
    for name in ("examples", "vocabularies"):
        shutil.copytree(REPO_ROOT / name, out_dir / name, dirs_exist_ok=True)

    g = merged_graph()
    g.serialize(destination=str(out_dir / "caveat-full.ttl"), format="turtle")
    g.serialize(destination=str(out_dir / "caveat.owl"), format="xml")
    for row in write_modes_csv(g, out_dir / "modes.csv"):
        if "|" in row["category_curies"]:
            print(f"note: {row['mode_curie']} is in more than one category: "
                  f"{row['category_curies']}", file=sys.stderr)
    return g


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    graph = build(Path(sys.argv[1]))
    print(f"built {len(graph)} triples into {sys.argv[1]}")
