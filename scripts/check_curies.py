#!/usr/bin/env python3
"""Report caveat:Name CURIEs that the ontology does not declare.

Usage:
    python scripts/check_curies.py PATH [PATH ...] [--ontology DIR] [--allow FILE]

Exit code 1 if any undeclared CURIE is found outside the allowlist.
Allowlist format: one CURIE or "path:CURIE" per line; '#' starts a comment.
"""
import argparse
import re
import sys
from pathlib import Path

from rdflib import Graph

NS = "https://w3id.org/intellicat/caveat#"
CURIE = re.compile(r"\bcaveat:([A-Za-z_][A-Za-z0-9_]*)")
EXTS = {".md", ".ttl", ".sparql", ".yaml", ".yml", ".py", ".json", ".jsonld", ".txt", ".html", ".template"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def declared_terms(ontology_dir: Path) -> set:
    g = Graph()
    for f in Path(ontology_dir).rglob("*.ttl"):
        g.parse(f, format="turtle")
    return {str(s)[len(NS):] for s in g.subjects() if str(s).startswith(NS)}


def iter_files(paths):
    for p in map(Path, paths):
        if p.is_file():
            yield p
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.suffix in EXTS and not SKIP_DIRS & set(f.parts):
                yield f


def load_allow(path):
    allow = set()
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                allow.add(line)
    return allow


def find_undeclared(paths, ontology_dir, allow):
    declared = declared_terms(ontology_dir)
    hits = []
    for f in iter_files(paths):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            for name in CURIE.findall(line):
                curie = f"caveat:{name}"
                if name in declared or curie in allow or f"{f.name}:{curie}" in allow:
                    continue
                hits.append((str(f), i, curie))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--ontology", default=str(Path(__file__).resolve().parent.parent / "src" / "ontology"))
    ap.add_argument("--allow")
    a = ap.parse_args(argv)
    hits = find_undeclared(a.paths, a.ontology, load_allow(a.allow))
    for f, i, c in hits:
        print(f"{f}:{i}: undeclared {c}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
