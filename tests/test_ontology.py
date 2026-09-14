"""CAVEAT ontology test suite.

Run with: python -m pytest tests/
Requires: pip install rdflib pyyaml pytest
"""

import json
import pytest
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS, OWL, RDF

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
VOCAB_DIR = REPO_ROOT / "vocabularies"


@pytest.fixture(scope="session")
def graph():
    """Load full CAVEAT ontology."""
    g = Graph()
    for ttl_file in ONTOLOGY_DIR.rglob("*.ttl"):
        g.parse(ttl_file, format="turtle")
    return g


def get_caveat_classes(g):
    """Get all OWL classes in the CAVEAT namespace."""
    for cls in g.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef) and str(cls).startswith(str(CAVEAT)):
            yield cls


class TestParsing:
    def test_all_ttl_files_parse(self):
        """All .ttl files must parse without errors."""
        for ttl_file in ONTOLOGY_DIR.rglob("*.ttl"):
            g = Graph()
            g.parse(ttl_file, format="turtle")  # Raises on parse error

    def test_nonzero_triples(self, graph):
        assert len(graph) > 100, "Ontology should have substantial content"


class TestLabelsAndDefinitions:
    def test_all_classes_have_labels(self, graph):
        for cls in get_caveat_classes(graph):
            label = graph.value(cls, RDFS.label)
            assert label is not None, f"Missing rdfs:label on {cls}"

    def test_unreliability_modes_have_definitions(self, graph):
        for cls in get_caveat_classes(graph):
            parents = set(graph.transitive_objects(cls, RDFS.subClassOf))
            if CAVEAT.UnreliabilityMode in parents:
                defn = graph.value(cls, CAVEAT.definition)
                assert defn is not None, f"Missing definition on {cls}"

    def test_detection_markers_have_definitions(self, graph):
        for cls in get_caveat_classes(graph):
            parents = set(graph.transitive_objects(cls, RDFS.subClassOf))
            if CAVEAT.DetectionMarker in parents:
                defn = graph.value(cls, CAVEAT.definition)
                assert defn is not None, f"Missing definition on {cls}"


class TestHierarchy:
    def test_four_top_level_categories(self, graph):
        """There should be exactly 4 direct children of UnreliabilityMode."""
        children = list(graph.subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode))
        caveat_children = [c for c in children if str(c).startswith(str(CAVEAT))]
        assert len(caveat_children) == 4, (
            f"Expected 4 top-level categories, got {len(caveat_children)}: "
            f"{[str(c) for c in caveat_children]}"
        )

    def test_top_level_categories_correct(self, graph):
        expected = {
            CAVEAT.DeliberateMisconduct,
            CAVEAT.PremiseLevelFailure,
            CAVEAT.InterpretiveFailure,
            CAVEAT.ExecutionLevelFailure,
        }
        children = set(graph.subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode))
        caveat_children = {c for c in children if str(c).startswith(str(CAVEAT))}
        assert caveat_children == expected


class TestEvidenceLinks:
    def test_all_evidence_links_have_strength(self, graph):
        for s, p, o in graph.triples((None, CAVEAT.evidenceFor, None)):
            strength = graph.value(s, CAVEAT.evidenceStrength)
            assert strength is not None, (
                f"Missing evidenceStrength on {s} -> {o}"
            )

    def test_evidence_strength_values_valid(self, graph):
        valid = {"definitive", "strong", "moderate", "weak"}
        for s, p, o in graph.triples((None, CAVEAT.evidenceStrength, None)):
            assert str(o) in valid, (
                f"Invalid evidenceStrength '{o}' on {s}. "
                f"Must be one of: {valid}"
            )


class TestLexiconFiles:
    def test_referenced_lexicon_files_exist(self, graph):
        lexicon_properties = (
            CAVEAT.lexiconFile,
            CAVEAT.retractionAwareLexiconFile,
        )
        for prop in lexicon_properties:
            for s, p, o in graph.triples((None, prop, None)):
                filepath = VOCAB_DIR / str(o)
                assert filepath.exists(), (
                    f"Lexicon file not found: {filepath} (referenced by {s} via {p})"
                )

    def test_lexicon_files_valid_yaml(self):
        import yaml
        for yaml_file in VOCAB_DIR.rglob("*.yaml"):
            if yaml_file.name == "_schema.yaml":
                continue
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            assert "domain" in data, f"Missing 'domain' in {yaml_file}"
            assert "terms" in data, f"Missing 'terms' in {yaml_file}"

    def test_lexicon_terms_have_classification(self):
        import yaml
        schema_path = VOCAB_DIR / "_schema.yaml"
        schema = yaml.safe_load(schema_path.read_text())
        allowed_classifications = set(
            schema["properties"]["terms"]["items"]["properties"]["classification"]["enum"]
        )
        for yaml_file in VOCAB_DIR.rglob("*.yaml"):
            if yaml_file.name == "_schema.yaml":
                continue
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            for term in data.get("terms", []):
                assert "term" in term, f"Missing 'term' field in {yaml_file}"
                assert "classification" in term, (
                    f"Missing 'classification' for term '{term.get('term')}' "
                    f"in {yaml_file}"
                )
                assert term["classification"] in allowed_classifications, (
                    f"Term '{term.get('term')}' in {yaml_file} has classification "
                    f"'{term.get('classification')}' not in schema enum"
                )

class TestSeverity:
    def test_severity_values_in_range(self, graph):
        for s, p, o in graph.triples((None, CAVEAT.defaultSeverity, None)):
            val = float(str(o))
            assert 0.0 <= val <= 1.0, (
                f"Severity {val} out of range [0,1] on {s}"
            )


class TestExamples:
    def test_example_files_parse(self):
        examples_dir = REPO_ROOT / "examples"
        found = list(examples_dir.rglob("*.ttl"))
        assert found, "No example .ttl files found"
        for ttl_file in found:
            Graph().parse(ttl_file, format="turtle")
