"""Version strings agree across the repository.

Rules:
  * the top CHANGELOG section is the version under development or just
    released; owl:versionInfo and docs/_config.yml carry that version;
  * CITATION.cff and dcterms:modified describe the latest *dated*
    CHANGELOG section;
  * CHANGELOG versions strictly decrease from top to bottom.
Use scripts/set_release.py to date a release.
"""
import re
from datetime import date
from pathlib import Path

import yaml
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL

ROOT = Path(__file__).resolve().parent.parent
HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] [-\u2014] (.+)$", re.M)


def sections():
    return [(v, d.strip()) for v, d in HEADING.findall((ROOT / "CHANGELOG.md").read_text())]


def as_tuple(v):
    return tuple(int(x) for x in v.split("."))


def test_changelog_order_and_dates():
    secs = sections()
    assert secs, "no version sections in CHANGELOG.md"
    versions = [as_tuple(v) for v, _ in secs]
    assert versions == sorted(versions, reverse=True) and len(set(versions)) == len(versions)
    for i, (v, d) in enumerate(secs):
        if d == "Unreleased":
            assert i == 0, f"only the top section may be unreleased, not {v}"
        else:
            date.fromisoformat(d)


def test_top_version_everywhere():
    top = sections()[0][0]
    g = Graph().parse(ROOT / "src" / "ontology" / "caveat.ttl", format="turtle")
    assert str(g.value(URIRef("https://w3id.org/intellicat/caveat"), OWL.versionInfo)) == top
    site = yaml.safe_load((ROOT / "docs" / "_config.yml").read_text())
    assert str(site["version"]) == top


def test_citation_matches_latest_release():
    released = [(v, d) for v, d in sections() if d != "Unreleased"]
    assert released, "no dated release in CHANGELOG.md"
    v, d = released[0]
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    assert str(cff["version"]) == v
    assert str(cff["date-released"]) == d


def test_modified_matches_latest_release():
    released = [(v, d) for v, d in sections() if d != "Unreleased"]
    g = Graph().parse(ROOT / "src" / "ontology" / "caveat.ttl", format="turtle")
    assert str(g.value(URIRef("https://w3id.org/intellicat/caveat"), DCTERMS.modified)) == released[0][1]
