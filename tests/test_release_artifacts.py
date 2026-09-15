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
    assert len(list((artifacts / "modules").glob("*.ttl"))) == 5
    assert len(list((artifacts / "imports").glob("*.ttl"))) == 2


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
