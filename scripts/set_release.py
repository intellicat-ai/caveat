#!/usr/bin/env python3
"""Date the top CHANGELOG section; update CITATION.cff and dcterms:modified.

Usage:
    python scripts/set_release.py VERSION YYYY-MM-DD

Requires the top CHANGELOG section to be "## [VERSION] - Unreleased", and
owl:versionInfo in src/ontology/caveat.ttl and `version` in
docs/_config.yml to equal VERSION already. Changes CHANGELOG.md, CITATION.cff and
dcterms:modified in src/ontology/caveat.ttl. Run tests/test_versions.py
afterwards.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        raise SystemExit(__doc__)
    version, day = argv
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"bad version {version!r}")
    date.fromisoformat(day)

    onto = (ROOT / "src/ontology/caveat.ttl").read_text()
    if f'owl:versionInfo "{version}"' not in onto:
        raise SystemExit(f"owl:versionInfo in src/ontology/caveat.ttl is not {version}")
    site = (ROOT / "docs/_config.yml").read_text()
    if not re.search(rf"^version: {re.escape(version)}$", site, re.M):
        raise SystemExit(f"docs/_config.yml version is not {version}")

    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text()
    top = re.search(r"^## \[([^\]]+)\] [-\u2014] (.+)$", text, re.M)
    if not top or top.group(1) != version or top.group(2).strip() != "Unreleased":
        raise SystemExit(f"top CHANGELOG section must be '## [{version}] - Unreleased'")
    cl.write_text(text[:top.start()] + f"## [{version}] - {day}" + text[top.end():])

    cff = ROOT / "CITATION.cff"
    c = cff.read_text()
    c, n1 = re.subn(r"^version: .*$", f"version: {version}", c, count=1, flags=re.M)
    c, n2 = re.subn(r"^date-released: .*$", f'date-released: "{day}"', c, count=1, flags=re.M)
    if n1 != 1 or n2 != 1:
        raise SystemExit("CITATION.cff lacks version or date-released")
    cff.write_text(c)

    onto, n3 = re.subn(r'dcterms:modified "[^"]*"\^\^xsd:date',
                       f'dcterms:modified "{day}"^^xsd:date', onto, count=1)
    if n3 != 1:
        raise SystemExit("src/ontology/caveat.ttl lacks dcterms:modified")
    (ROOT / "src/ontology/caveat.ttl").write_text(onto)
    print(f"CHANGELOG.md, CITATION.cff and dcterms:modified set to {version} ({day})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
