"""Release artifacts build, parse, and agree with source.

The artifacts are generated at publish time, not committed. This builds them
into a tmp dir with the same code the Pages workflow runs, then checks that
every serialization round-trips to the same graph.
"""
import sys
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_artifacts import build, merged_graph  # noqa: E402


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    out = tmp_path_factory.mktemp("artifacts")
    build(out)
    return out


def test_expected_files_exist(artifacts):
    for rel in ("caveat.ttl", "caveat-full.ttl", "caveat.owl"):
        assert (artifacts / rel).exists(), f"missing {rel}"
    src = REPO_ROOT / "src" / "ontology"
    expected = {f.name for f in (src / "modules").glob("*.ttl")}
    expected |= {f.name for f in (REPO_ROOT / "mappings" / "openalex").glob("*.ttl")}
    assert {f.name for f in (artifacts / "modules").glob("*.ttl")} == expected
    assert {f.name for f in (artifacts / "imports").glob("*.ttl")} == {
        f.name for f in (src / "imports").glob("*.ttl")}
    for d in ("examples", "vocabularies"):
        assert {p.relative_to(artifacts / d) for p in (artifacts / d).rglob("*") if p.is_file()} == {
            p.relative_to(REPO_ROOT / d) for p in (REPO_ROOT / d).rglob("*") if p.is_file()}


def test_full_turtle_matches_source(artifacts):
    published = Graph()
    published.parse(artifacts / "caveat-full.ttl", format="turtle")
    assert isomorphic(published, merged_graph())


def test_rdfxml_matches_turtle(artifacts):
    ttl, owl = Graph(), Graph()
    ttl.parse(artifacts / "caveat-full.ttl", format="turtle")
    owl.parse(artifacts / "caveat.owl", format="xml")
    assert isomorphic(ttl, owl), "RDF/XML serialization is not round-trip safe"


def test_root_is_copy_of_source(artifacts):
    a, b = Graph(), Graph()
    a.parse(artifacts / "caveat.ttl", format="turtle")
    b.parse(REPO_ROOT / "src" / "ontology" / "caveat.ttl", format="turtle")
    assert isomorphic(a, b)
