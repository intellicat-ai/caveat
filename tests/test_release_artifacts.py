"""Tests for CAVEAT release artifacts and metadata synchronization."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, RDF

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
SCRIPTS_DIR = REPO_ROOT / "scripts"
ROOT_ONTOLOGY = URIRef("https://w3id.org/intellicat/caveat")

# Load scripts/build_release.py dynamically since scripts/ is not a package
spec = importlib.util.spec_from_file_location(
    "build_release", SCRIPTS_DIR / "build_release.py"
)
build_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_release)


@pytest.fixture(scope="module")
def built_graph():
    return build_release.build_graph()


@pytest.fixture(scope="module")
def ttl_graph():
    ttl_path = DOCS_DIR / "caveat.ttl"
    assert ttl_path.exists(), f"{ttl_path} does not exist"
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return g


@pytest.fixture(scope="module")
def owl_graph():
    owl_path = DOCS_DIR / "caveat.owl"
    assert owl_path.exists(), f"{owl_path} does not exist"
    g = Graph()
    g.parse(owl_path, format="xml")
    return g


@pytest.fixture(scope="module")
def cff_version():
    cff_path = REPO_ROOT / "CITATION.cff"
    assert cff_path.exists(), f"{cff_path} does not exist"
    data = yaml.safe_load(cff_path.read_text(encoding="utf-8"))
    return str(data["version"])


def test_artifacts_parse_and_are_isomorphic(built_graph, ttl_graph, owl_graph):
    """Both files parse and are isomorphic to freshly built graph."""
    assert isomorphic(built_graph, ttl_graph), "docs/caveat.ttl is not isomorphic to freshly built graph"
    assert isomorphic(built_graph, owl_graph), "docs/caveat.owl is not isomorphic to freshly built graph"


def test_single_ontology_declaration(built_graph):
    """The merged graph has exactly one owl:Ontology and its IRI is https://w3id.org/intellicat/caveat."""
    ontologies = list(built_graph.subjects(RDF.type, OWL.Ontology))
    assert len(ontologies) == 1, f"Expected 1 owl:Ontology, got {len(ontologies)}: {ontologies}"
    assert ontologies[0] == ROOT_ONTOLOGY, f"Expected ontology IRI {ROOT_ONTOLOGY}, got {ontologies[0]}"


def test_zero_owl_imports(built_graph):
    """The merged graph has zero owl:imports."""
    imports = list(built_graph.triples((None, OWL.imports, None)))
    assert len(imports) == 0, f"Expected zero owl:imports, got: {imports}"


def test_version_info_matches_citation(built_graph, cff_version):
    """owl:versionInfo on https://w3id.org/intellicat/caveat equals version in CITATION.cff."""
    version_info = built_graph.value(ROOT_ONTOLOGY, OWL.versionInfo)
    assert version_info is not None, "Missing owl:versionInfo on root ontology"
    assert str(version_info) == cff_version, (
        f"owl:versionInfo ({version_info}) does not match CITATION.cff version ({cff_version})"
    )


def test_config_version_matches_citation(cff_version):
    """version in docs/_config.yml equals version in CITATION.cff."""
    config_path = DOCS_DIR / "_config.yml"
    assert config_path.exists(), f"{config_path} does not exist"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "version" in data, "docs/_config.yml missing 'version' key"
    assert str(data["version"]) == cff_version, (
        f"docs/_config.yml version ({data['version']}) does not match CITATION.cff version ({cff_version})"
    )
