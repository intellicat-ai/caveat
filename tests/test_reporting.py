"""Assessment reporting layer: module, profile files and payload checker.

Expected values come from design/reporting.yaml.
"""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "design" / "reporting.yaml").read_text())
PROFILES = ROOT / "vocabularies" / "profiles"
EXAMPLES = sorted((PROFILES / "examples").glob("*.json"))
TAXONOMY = ROOT / "mappings" / "openalex" / "openalex.ttl"
KINDS = {"ObjectProperty": OWL.ObjectProperty, "DatatypeProperty": OWL.DatatypeProperty,
         "AnnotationProperty": OWL.AnnotationProperty}


def norm(s):
    return " ".join(str(s).split())


def load(name):
    spec = importlib.util.spec_from_file_location(f"_reporting_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def g():
    graph = Graph()
    for f in (ROOT / "src" / "ontology").rglob("*.ttl"):
        graph.parse(f, format="turtle")
    return graph


@pytest.fixture(scope="module")
def ca():
    return load("check_assessment")


# --------------------------------------------------------------------------- TBox

def test_module_file_and_import(g):
    assert (ROOT / "src" / "ontology" / "modules" / "assessment.ttl").exists()
    assert (URIRef("https://w3id.org/intellicat/caveat"), OWL.imports,
            URIRef("https://w3id.org/intellicat/caveat/modules/assessment")) in g


@pytest.mark.parametrize("c", SPEC["classes"], ids=lambda c: c["id"])
def test_classes(g, c):
    n = CAVEAT[c["id"]]
    assert (n, RDF.type, OWL.Class) in g
    assert str(g.value(n, RDFS.label)) == c["label"]
    assert norm(g.value(n, CAVEAT.definition)) == norm(c["definition"])
    if "parent_iri" in c:
        assert (n, RDFS.subClassOf, URIRef(c["parent_iri"])) in g


@pytest.mark.parametrize("r", SPEC["topic_relations"], ids=lambda r: r["id"])
def test_topic_relations(g, r):
    n = CAVEAT[r["id"]]
    assert (n, RDF.type, CAVEAT.TopicRelation) in g
    assert (n, RDF.type, OWL.NamedIndividual) in g
    assert str(g.value(n, RDFS.label)) == r["label"]
    assert int(g.value(n, CAVEAT.levelRank)) == r["level_rank"]
    assert norm(g.value(n, CAVEAT.definition)) == norm(r["definition"])


def test_only_spec_topic_relations(g):
    got = {str(s).split("#")[1] for s in g.subjects(RDF.type, CAVEAT.TopicRelation)}
    assert got == {r["id"] for r in SPEC["topic_relations"]}


@pytest.mark.parametrize("p", SPEC["properties"], ids=lambda p: p["id"])
def test_properties(g, p):
    n = CAVEAT[p["id"]]
    assert (n, RDF.type, KINDS[p["kind"]]) in g
    assert str(g.value(n, RDFS.label)) == p["label"]
    assert (n, RDFS.domain, CAVEAT[p["domain"]]) in g
    if "range" in p:
        assert (n, RDFS.range, CAVEAT[p["range"]]) in g
    if "range_iri" in p:
        assert (n, RDFS.range, URIRef(p["range_iri"])) in g


# --------------------------------------------------------------------------- files

def test_profile_files_exist():
    for rel in SPEC["profile_files"]:
        assert (ROOT / rel).is_file(), rel

def test_release_ships_profiles(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_artifacts import build
    build(tmp_path)
    for rel in SPEC["profile_files"]:
        if rel.startswith("vocabularies/"):
            assert (tmp_path / rel).is_file(), rel


def test_profile_iris():
    ctx_iri = SPEC["context_iri"]
    for path in EXAMPLES:
        assert json.loads(path.read_text())["@context"] == ctx_iri, path.name
    schema = json.loads((PROFILES / "assessment-1.schema.json").read_text())
    assert schema["$id"] == ctx_iri.rsplit("/", 1)[0] + "/assessment-1.schema.json"

# --------------------------------------------------------------------------- examples

def test_examples_present():
    assert {p.name for p in EXAMPLES} == {
        "spectra-fabrication.json", "citation-anomaly-graded.json", "retraction-stated-reason.json"}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_valid(g, ca, path):
    tax = Graph().parse(TAXONOMY, format="turtle") if TAXONOMY.exists() else None
    assert ca.check(json.loads(path.read_text()), g, tax) == []


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_expand_to_rdf(path):
    ctx = json.loads((PROFILES / "assessment-1.jsonld").read_text())["@context"]
    doc = json.loads(path.read_text())
    doc["@context"] = ctx
    r = Graph().parse(data=json.dumps(doc), format="json-ld")
    subj = URIRef(doc["document"])
    assessments = list(r.subjects(CAVEAT.assessedDocument, subj))
    assert len(assessments) == len(doc["assessments"])
    for a in assessments:
        assert r.value(a, CAVEAT.assessedMode) is not None
        obs = list(r.objects(a, CAVEAT.supportedBy))
        assert obs
        for o in obs:
            assert r.value(o, CAVEAT.observedMarker) is not None
            assert r.value(o, CAVEAT.appliedLink) is not None
            det = r.value(o, CAVEAT.detectedBy)
            assert r.value(det, CAVEAT.detectorModule) is not None
            loc = r.value(o, CAVEAT.evidenceLocator)
            assert loc is not None and str(loc.datatype).endswith("#JSON")


# --------------------------------------------------------------------------- negative cases

def base():
    return json.loads((PROFILES / "examples" / "spectra-fabrication.json").read_text())


def graded():
    return json.loads((PROFILES / "examples" / "citation-anomaly-graded.json").read_text())


def stated():
    return json.loads((PROFILES / "examples" / "retraction-stated-reason.json").read_text())


def obs(d):
    return d["assessments"][0]["observations"][0]


def mutate(d, fn):
    d = copy.deepcopy(d)
    fn(d)
    return d


CASES = [
    ("link_of_other_marker", base, lambda d: obs(d).update(marker="caveat:ClonedImages"), "does not belong"),
    ("mode_not_supported", base, lambda d: d["assessments"][0].update(mode="caveat:Falsification"), "does not support"),
    ("strength_mismatch", base, lambda d: obs(d).update(strength="caveat:WeakEvidence"), "expected"),
    ("graded_strength_given", base, lambda d: obs(d).update(strength="caveat:GradedEvidence"), "ranked strength"),
    ("graded_without_intensity", graded, lambda d: obs(d).pop("intensity"), "requires intensity"),
    ("graded_wrong_band", graded, lambda d: obs(d).update(intensity=0.3), "expected"),
    ("stated_without_mode", stated, lambda d: obs(d).pop("stated_mode"), "requires stated_mode"),
    ("fixed_with_stated_mode", base, lambda d: obs(d).update(stated_mode="caveat:Fabrication"), "only allowed"),
    ("stated_mode_mismatch", stated, lambda d: obs(d).update(stated_mode="caveat:TextPlagiarism"), "does not support"),
    ("marker_is_mode", base, lambda d: obs(d).update(marker="caveat:Fabrication"), "not a detection marker"),
    ("bad_relation_key", graded, lambda d: obs(d)["topic_relation_counts"].update({"caveat:Fabrication": 1}), "not a topic relation"),
    ("newer_version", base, lambda d: d.update(caveat_version="99.0.0"), "newer"),
    ("schema_extra_key", base, lambda d: obs(d).update(foo=1), "schema"),
    ("schema_confidence_range", base, lambda d: obs(d).update(confidence=1.5), "schema"),
]


@pytest.mark.parametrize("name,make,fn,needle", CASES, ids=[c[0] for c in CASES])
def test_negative(g, ca, name, make, fn, needle):
    errs = ca.check(mutate(make(), fn), g)
    assert errs, f"{name} was accepted"
    assert any(needle in e for e in errs), errs


def test_ancestor_mode_accepted(g, ca):
    d = mutate(base(), lambda d: d["assessments"][0].update(mode="caveat:DataMisconduct"))
    assert ca.check(d, g) == []


def test_band_edges(g, ca):
    assert ca.band(g, 0.0) == CAVEAT.WeakEvidence
    assert ca.band(g, 0.25) == CAVEAT.ModerateEvidence
    assert ca.band(g, 0.4999) == CAVEAT.ModerateEvidence
    assert ca.band(g, 0.5) == CAVEAT.StrongEvidence
    assert ca.band(g, 0.75) == CAVEAT.DefinitiveEvidence
    assert ca.band(g, 1.0) == CAVEAT.DefinitiveEvidence
