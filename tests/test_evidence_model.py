"""Evidence model, multi-parent vocabulary resolution, hierarchy and CURIE checks.

Expected values come from design/evidence-model.yaml. To change one, change
the spec and the ontology together.
"""

import importlib.util
import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
IAO_ICE = URIRef("http://purl.obolibrary.org/obo/IAO_0000030")
ROOT = Path(__file__).resolve().parent.parent
ONT = ROOT / "src" / "ontology"
SPEC = yaml.safe_load((ROOT / "design" / "evidence-model.yaml").read_text())


def norm(s):
    return " ".join(str(s).split())


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_evidence_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def g():
    graph = Graph()
    for f in ONT.rglob("*.ttl"):
        graph.parse(f, format="turtle")
    return graph


def en(g, s, p):
    vals = [o for o in g.objects(s, p)]
    assert len(vals) == 1, f"{s} needs exactly one {p}, has {vals}"
    return vals[0]


# --------------------------------------------------------------------------- strengths

def test_strength_class(g):
    c = CAVEAT[SPEC["strength_class"]["id"]]
    assert (c, RDF.type, OWL.Class) in g
    assert str(en(g, c, RDFS.label)) == SPEC["strength_class"]["label"]
    assert norm(en(g, c, CAVEAT.definition)) == norm(SPEC["strength_class"]["definition"])


@pytest.mark.parametrize("s", SPEC["strengths"], ids=lambda s: s["id"])
def test_strength_individual(g, s):
    i = CAVEAT[s["id"]]
    assert (i, RDF.type, CAVEAT.EvidenceStrength) in g
    assert (i, RDF.type, OWL.NamedIndividual) in g
    assert str(en(g, i, RDFS.label)) == s["label"]
    assert norm(en(g, i, CAVEAT.definition)) == norm(s["definition"])
    if "rank" in s:
        assert int(en(g, i, CAVEAT.strengthRank)) == s["rank"]
        assert Decimal(str(en(g, i, CAVEAT.intensityLowerBound))) == Decimal(s["intensity_lower_bound"])
    else:
        assert g.value(i, CAVEAT.strengthRank) is None
        assert g.value(i, CAVEAT.intensityLowerBound) is None


def test_only_spec_strengths_exist(g):
    got = {str(s).split("#")[1] for s in g.subjects(RDF.type, CAVEAT.EvidenceStrength)}
    assert got == {s["id"] for s in SPEC["strengths"]}


# --------------------------------------------------------------------------- classes and properties

@pytest.mark.parametrize("c", SPEC["link_classes"], ids=lambda c: c["id"])
def test_link_classes(g, c):
    node = CAVEAT[c["id"]]
    assert (node, RDF.type, OWL.Class) in g
    parent = URIRef(c["parent_iri"]) if "parent_iri" in c else CAVEAT[c["parent"]]
    assert (node, RDFS.subClassOf, parent) in g
    assert str(en(g, node, RDFS.label)) == c["label"]
    assert norm(en(g, node, CAVEAT.definition)) == norm(c["definition"])


KINDS = {"ObjectProperty": OWL.ObjectProperty, "AnnotationProperty": OWL.AnnotationProperty,
         "DatatypeProperty": OWL.DatatypeProperty}


@pytest.mark.parametrize("p", SPEC["properties"], ids=lambda p: p["id"])
def test_properties(g, p):
    node = CAVEAT[p["id"]]
    assert (node, RDF.type, KINDS[p["kind"]]) in g
    other_kinds = set(KINDS.values()) - {KINDS[p["kind"]]}
    for k in other_kinds:
        assert (node, RDF.type, k) not in g, f"{p['id']} also typed {k}"
    assert str(en(g, node, RDFS.label)) == p["label"]
    if "domain" in p:
        assert (node, RDFS.domain, CAVEAT[p["domain"]]) in g
    if "range" in p:
        assert (node, RDFS.range, CAVEAT[p["range"]]) in g
    if "range_iri" in p:
        assert (node, RDFS.range, URIRef(p["range_iri"])) in g


# --------------------------------------------------------------------------- links

def link_nodes(g):
    return set(g.subjects(RDF.type, CAVEAT.EvidenceLink)) | set(
        g.subjects(RDF.type, CAVEAT.StatedReasonEvidenceLink))


def test_fixed_links_exact(g):
    got = set()
    for n in link_nodes(g):
        if (n, RDF.type, CAVEAT.StatedReasonEvidenceLink) in g:
            continue
        m = en(g, n, CAVEAT.linkMarker)
        mode = en(g, n, CAVEAT.linkMode)
        st = en(g, n, CAVEAT.evidenceStrength)
        local = lambda u: str(u).split("#")[1]
        assert str(n) == str(CAVEAT[f"evidence_{local(m)}_{local(mode)}"]), f"bad IRI {n}"
        assert g.value(n, RDFS.label) is None, f"link {n} must not have a label"
        got.add((local(m), local(mode), local(st)))
    want = {tuple(x) for x in SPEC["fixed_links"]}
    assert got == want, f"missing {sorted(want - got)}; extra {sorted(got - want)}"


def test_stated_reason_links_exact(g):
    got = set()
    for n in g.subjects(RDF.type, CAVEAT.StatedReasonEvidenceLink):
        m = en(g, n, CAVEAT.linkMarker)
        assert g.value(n, CAVEAT.linkMode) is None, f"{n} must not have linkMode"
        st = en(g, n, CAVEAT.evidenceStrength)
        local = lambda u: str(u).split("#")[1]
        assert str(n) == str(CAVEAT[f"evidence_{local(m)}_stated"])
        got.add((local(m), local(st)))
    assert got == {tuple(x) for x in SPEC["stated_reason_links"]}


def test_evidence_for_is_projection(g):
    proj = {(str(g.value(n, CAVEAT.linkMarker)), str(g.value(n, CAVEAT.linkMode)))
            for n in link_nodes(g)
            if (n, RDF.type, CAVEAT.StatedReasonEvidenceLink) not in g}
    direct = {(str(s), str(o)) for s, o in g.subject_objects(CAVEAT.evidenceFor)}
    assert direct == proj


def test_strength_only_on_links(g):
    nodes = link_nodes(g)
    for s in g.subjects(CAVEAT.evidenceStrength, None):
        assert s in nodes, f"evidenceStrength on non-link {s}"
    for o in g.objects(None, CAVEAT.evidenceStrength):
        assert not isinstance(o, Literal), f"literal strength {o!r}"


def test_link_endpoints_are_markers_and_modes(g):
    for n in link_nodes(g):
        m = g.value(n, CAVEAT.linkMarker)
        assert CAVEAT.DetectionMarker in set(g.transitive_objects(m, RDFS.subClassOf)), m
        mode = g.value(n, CAVEAT.linkMode)
        if mode is not None:
            assert CAVEAT.UnreliabilityMode in set(g.transitive_objects(mode, RDFS.subClassOf)), mode


CQ5 = """
PREFIX caveat: <https://w3id.org/intellicat/caveat#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?mode ?strength WHERE {
  ?link a caveat:EvidenceLink ;
        caveat:linkMarker caveat:ImpossibleStatistics ;
        caveat:linkMode ?mode ;
        caveat:evidenceStrength ?s .
  ?s rdfs:label ?strength .
}
"""


def test_cq5_no_cross_product(g):
    rows = {(str(r.mode).split("#")[1], str(r.strength)) for r in g.query(CQ5)}
    assert rows == {("Fabrication", "moderate"), ("Falsification", "moderate"),
                    ("StatisticalMalpractice", "weak")}


# --------------------------------------------------------------------------- other edits

def test_mappings_readme_names_only_real_scripts():
    text = (ROOT / "mappings" / "README.md").read_text()
    for name in re.findall(r"scripts/([\w\-]+\.py)", text):
        assert (ROOT / "scripts" / name).exists(), f"mappings/README.md names missing scripts/{name}"


# --------------------------------------------------------------------------- polyhierarchy readiness

def synthetic_graph():
    t = Graph()
    A, B, C, D, E, R = (CAVEAT[f"EvTest{x}"] for x in "ABCDER")
    t.add((A, RDFS.subClassOf, B)); t.add((A, RDFS.subClassOf, C)); t.add((A, RDFS.subClassOf, D))
    t.add((B, RDFS.subClassOf, R)); t.add((C, RDFS.subClassOf, R)); t.add((D, RDFS.subClassOf, E))
    t.add((E, RDFS.subClassOf, R))
    for node, f in ((A, "a.yaml"), (C, "c.yaml"), (B, "b.yaml"), (E, "e.yaml"), (R, "r.yaml")):
        t.add((node, CAVEAT.lexiconFile, Literal(f)))
    return t, A


def test_resolve_vocabulary_dag_order():
    mod = load_script("resolve_vocabulary")
    t, A = synthetic_graph()
    # Distances: B, C, D = 1 (D has no lexicon); E (via D) and R (via B, C) = 2.
    # Nearest first, ties broken by IRI (EvTestE < EvTestR), each file once.
    assert mod.resolve_lexicon_files(t, A) == ["a.yaml", "b.yaml", "c.yaml", "e.yaml", "r.yaml"]


def test_resolve_vocabulary_real_chain_unchanged(g):
    mod = load_script("resolve_vocabulary")
    got = mod.resolve_lexicon_files(g, CAVEAT.BiofieldEnergyHealing)
    assert got[:3] == ["engagement/biofield-energy-healing.yaml",
                       "engagement/vitalist-energy-medicine.yaml",
                       "rejection/pseudoscience-base.yaml"]


def test_validator_hierarchy_check():
    mod = load_script("validate")
    t = Graph()
    X, Y, Z, O = (CAVEAT[f"EvVal{x}"] for x in "XYZO")
    for n in (X, Y, Z, O):
        t.add((n, RDF.type, OWL.Class))
    t.add((X, RDFS.subClassOf, Y)); t.add((Y, RDFS.subClassOf, X))  # cycle
    t.add((Z, RDFS.subClassOf, CAVEAT.UnreliabilityMode))
    t.add((Z, RDFS.subClassOf, CAVEAT.EvValNothing))  # parent that is not a declared class
    errs = mod.check_hierarchy(t)
    joined = "\n".join(errs)
    assert "cycle" in joined.lower()
    assert "EvValO" in joined  # orphan: no CAVEAT parent
    assert "EvValNothing" in joined  # undeclared parent


def test_validator_hierarchy_clean_on_repo(g):
    mod = load_script("validate")
    assert mod.check_hierarchy(g) == []


# --------------------------------------------------------------------------- CURIE checker

def test_curie_checker_clean_on_repo(g):
    mod = load_script("check_curies")
    assert mod.main([str(ROOT), "--ontology", str(ONT),
                     "--allow", str(ROOT / ".caveat-curie-allowlist")]) == 0


def test_curie_checker_catches(tmp_path, g):
    mod = load_script("check_curies")
    f = tmp_path / "x.md"
    f.write_text("see caveat:Fabrication and caveat:NotARealClass here\n")
    hits = mod.find_undeclared([tmp_path], ONT, allow=set())
    assert [(h[2]) for h in hits] == ["caveat:NotARealClass"]
    assert hits[0][1] == 1  # 1-based line number


def test_readme_links_exist():
    for doc in ("README.md", "CONTRIBUTING.md"):
        text = (ROOT / doc).read_text()
        for rel in re.findall(r"\]\(((?:docs|design|scripts|vocabularies)/[^)#]+)\)", text):
            assert (ROOT / rel).exists(), f"{doc} links missing {rel}"
