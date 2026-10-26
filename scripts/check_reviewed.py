#!/usr/bin/env python3
"""Check that agent-authored records carry a human review.

A record passes when its annotator and reviewer are non-empty and the
reviewer's initials are listed in .reviewers. The reviewer must differ
from the annotator unless the annotator is a listed person (self-review,
allowed while CAVEAT has a single maintainer). Records checked:

1. Lexicon files, vocabularies/**/*.yaml: top-level
   annotation: {annotator, reviewer}
2. Committed proposal records, design/proposals/*.yaml: the same
   annotation block; every exemplar also needs a non-empty prior_record
3. Rebuttal manifest rows, mappings/rebuttals/manifest.jsonl:
   annotator and reviewer fields on every row
4. Mode-domain rows, mappings/openalex/mode-domains.csv:
   annotator and reviewer columns on every row

Files that do not exist yet are skipped. The check cannot tell initials
typed by a person from initials typed by an agent; see docs/review.md.

Usage:
    python scripts/check_reviewed.py [--root DIR]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_reviewers(root: Path) -> set[str]:
    path = root / ".reviewers"
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line.casefold())
    return out


def check_pair(where: str, annotator, reviewer, reviewers: set[str]) -> list[str]:
    annotator = str(annotator or "").strip()
    reviewer = str(reviewer or "").strip()
    if not annotator:
        return [f"{where}: annotator is empty"]
    if not reviewer:
        return [f"{where}: not reviewed (reviewer is empty)"]
    # Self-review is allowed only for a listed person, while CAVEAT has a
    # single maintainer. Revisit when a second reviewer joins.
    if reviewer.casefold() == annotator.casefold() and annotator.casefold() not in reviewers:
        return [f"{where}: reviewer '{reviewer}' is also the annotator"]
    if reviewer.casefold() not in reviewers:
        return [f"{where}: reviewer '{reviewer}' is not listed in .reviewers"]
    return []


def check_annotation_block(where: str, data, reviewers: set[str]) -> list[str]:
    ann = data.get("annotation") if isinstance(data, dict) else None
    if not isinstance(ann, dict):
        return [f"{where}: missing annotation block"]
    return check_pair(where, ann.get("annotator"), ann.get("reviewer"), reviewers)


def exemplars(data) -> list:
    """Exemplar entries in a proposal record, wherever they are listed."""
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "exemplars" and isinstance(v, list):
                found += v
            elif k == "sources" and isinstance(v, list):
                found += [s for s in v if isinstance(s, dict) and s.get("role") == "exemplar"]
            else:
                found += exemplars(v)
    elif isinstance(data, list):
        for v in data:
            found += exemplars(v)
    return found


def check(root: Path) -> list[str]:
    reviewers = load_reviewers(root)
    errors = []
    if not reviewers:
        errors.append(".reviewers is missing or empty")

    for f in sorted((root / "vocabularies").rglob("*.yaml")):
        if f.name == "_schema.yaml":
            continue
        rel = f.relative_to(root)
        errors += check_annotation_block(str(rel), yaml.safe_load(f.read_text()), reviewers)

    for f in sorted((root / "design" / "proposals").glob("*.yaml")):
        rel = f.relative_to(root)
        data = yaml.safe_load(f.read_text())
        errors += check_annotation_block(str(rel), data, reviewers)
        for i, ex in enumerate(exemplars(data)):
            if not (isinstance(ex, dict) and ex.get("prior_record")):
                ref = ex.get("ref", i) if isinstance(ex, dict) else i
                errors.append(f"{rel}: exemplar {ref} has no prior_record")

    manifest = root / "mappings" / "rebuttals" / "manifest.jsonl"
    if manifest.exists():
        rel = manifest.relative_to(root)
        for n, line in enumerate(manifest.read_text().splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            errors += check_pair(f"{rel}:{n}", row.get("annotator"), row.get("reviewer"), reviewers)

    domains = root / "mappings" / "openalex" / "mode-domains.csv"
    if domains.exists():
        rel = domains.relative_to(root)
        with domains.open(newline="") as fh:
            for n, row in enumerate(csv.DictReader(fh), 2):
                errors += check_pair(f"{rel}:{n}", row.get("annotator"), row.get("reviewer"), reviewers)

    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    args = ap.parse_args()
    errors = check(args.root)
    if errors:
        print(f"{len(errors)} unreviewed or invalid record(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    print("✓ All agent-authored records are reviewed")


if __name__ == "__main__":
    main()
