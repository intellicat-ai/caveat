"""Mode domains, mode associations, rebuttal links and the modes.csv export.

Expected values come from design/mode-links.yaml. To change one, change the
spec and the ontology together.
"""

import csv
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
ROOT = Path(__file__).resolve().parent.parent
ONT = ROOT / "src" / "ontology"
SPEC = yaml.safe_load((ROOT / "design" / "mode-links.yaml").read_text())
MODE_DOMAINS = ROOT / "mappings" / "openalex" / "mode-domains.csv"
MANIFEST = ROOT / "mappings" / "rebuttals" / "manifest.jsonl"
MANIFEST_SCHEMA = ROOT / "mappings" / "rebuttals" / "manifest.schema.json"

sys.path.insert(0, str(ROOT / "scripts"))
from build_artifacts import MODES_COLUMNS, curie, finding_code, modes_rows  # noqa: E402

KINDS = {"ObjectProperty": OWL.ObjectProperty, "AnnotationProperty": OWL.AnnotationProperty,
         "DatatypeProperty": OWL.DatatypeProperty}


@pytest.fixture(scope="module")
def g():
    graph = Graph()
    for f in ONT.rglob("*.ttl"):
        graph.parse(f, format="turtle")
    return graph


@pytest.fixture(scope="module")
def taxonomy():
    return Graph().parse(ROOT / "mappings" / "openalex" / "openalex.ttl", format="turtle")


def local(u):
    return str(u).split("#", 1)[1]


def modes(g):
    return set(g.transitive_subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode)) - {CAVEAT.UnreliabilityMode}


def ancestors(g, c):
    return set(g.transitive_objects(c, RDFS.subClassOf)) - {c}


def one(g, s, p):
    vals = list(g.objects(s, p))
    assert len(vals) == 1, f"{s} needs exactly one {p}, has {vals}"
    return vals[0]


def manifest_rows():
    lines = MANIFEST.read_text().splitlines() if MANIFEST.exists() else []
    return [json.loads(line) for line in lines if line.strip()]


def mode_domain_rows():
    with MODE_DOMAINS.open(newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- declarations

@pytest.mark.parametrize("p", SPEC["properties"], ids=lambda p: p["id"])
def test_properties(g, p):
    node = CAVEAT[p["id"]]
    assert (node, RDF.type, KINDS[p["kind"]]) in g
    for k in set(KINDS.values()) - {KINDS[p["kind"]]}:
        assert (node, RDF.type, k) not in g, f"{p['id']} also typed {k}"
    assert str(one(g, node, RDFS.label)) == p["label"]
    if "sub_property_of" in p:
        assert (node, RDFS.subPropertyOf, CAVEAT[p["sub_property_of"]]) in g
    if "domain" in p:
        assert (node, RDFS.domain, CAVEAT[p["domain"]]) in g
    if "range" in p:
        assert (node, RDFS.range, CAVEAT[p["range"]]) in g


def test_link_class(g):
    c = SPEC["link_class"]
    node = CAVEAT[c["id"]]
    assert (node, RDF.type, OWL.Class) in g
    assert (node, RDFS.subClassOf, URIRef(c["parent_iri"])) in g
    assert str(one(g, node, RDFS.label)) == c["label"]
    assert one(g, node, CAVEAT.definition)


@pytest.mark.parametrize("c", SPEC["kind_classes"], ids=lambda c: c["id"])
def test_kind_classes(g, c):
    node = CAVEAT[c["id"]]
    assert (node, RDF.type, OWL.Class) in g
    assert str(one(g, node, RDFS.label)) == c["label"]
    assert one(g, node, CAVEAT.definition)
    if "parent" in c:
        assert (node, RDFS.subClassOf, CAVEAT[c["parent"]]) in g


@pytest.mark.parametrize("k", SPEC["kinds"], ids=lambda k: k["id"])
def test_kind_individuals(g, k):
    node = CAVEAT[k["id"]]
    assert (node, RDF.type, OWL.NamedIndividual) in g
    assert set(g.objects(node, RDF.type)) == {OWL.NamedIndividual, CAVEAT[k["tier"]]}
    assert str(one(g, node, RDFS.label)) == k["label"]
    assert one(g, node, CAVEAT.definition)


def test_only_spec_kinds_exist(g):
    got = set()
    for tier in ("PrimaryRebuttalKind", "SecondaryRebuttalKind", "RebuttalKind"):
        got |= {local(s) for s in g.subjects(RDF.type, CAVEAT[tier])}
    assert got == {k["id"] for k in SPEC["kinds"]}


# --------------------------------------------------------------------------- mode domains

def test_candidate_domain_is_abstract(g):
    assert not list(g.subject_objects(CAVEAT.candidateDomain))


@pytest.mark.parametrize("prop", ["dedicatedDomain", "hostDomain"])
def test_domain_values(g, taxonomy, prop):
    levels = {CAVEAT[lvl] for lvl in SPEC["domain_levels"]}
    all_modes = modes(g)
    for mode, topic in g.subject_objects(CAVEAT[prop]):
        assert mode in all_modes, f"{prop} on non-mode {mode}"
        assert set(taxonomy.objects(topic, RDF.type)) & levels, \
            f"{local(mode)} {prop} {topic} is not a topic or subfield in the pinned taxonomy"


def test_dedicated_cardinality(g):
    per_mode, per_topic = {}, {}
    for mode, topic in g.subject_objects(CAVEAT.dedicatedDomain):
        per_mode.setdefault(mode, set()).add(topic)
        per_topic.setdefault(topic, set()).add(mode)
    assert all(len(v) == 1 for v in per_mode.values()), per_mode
    assert all(len(v) == 1 for v in per_topic.values()), per_topic


def test_dedicated_is_not_also_host(g):
    both = set(g.subject_objects(CAVEAT.dedicatedDomain)) & set(g.subject_objects(CAVEAT.hostDomain))
    assert not both


def test_mode_domains_columns():
    with MODE_DOMAINS.open(newline="") as fh:
        assert next(csv.reader(fh)) == SPEC["mode_domains_columns"]


def test_mode_domains_match_ontology(g):
    """Every assertion has its measured row and every row has its assertion."""
    oa = "https://w3id.org/intellicat/caveat/modules/openalex#"
    asserted = set()
    for kind, prop in (("dedicated", CAVEAT.dedicatedDomain), ("host", CAVEAT.hostDomain)):
        for mode, topic in g.subject_objects(prop):
            asserted.add((f"caveat:{local(mode)}", "caveatoa:" + str(topic)[len(oa):], kind))
    rows = {(r["mode"], r["topic"], r["kind"]) for r in mode_domain_rows()}
    assert rows == asserted


# --------------------------------------------------------------------------- associations

def test_related_mode_ends_are_modes(g):
    all_modes = modes(g)
    for prop in (CAVEAT.relatedMode, CAVEAT.typicallyExhibits):
        for a, b in g.subject_objects(prop):
            assert a in all_modes and b in all_modes, (a, prop, b)
            assert a != b, f"{a} linked to itself"


def test_related_mode_symmetric(g):
    pairs = set(g.subject_objects(CAVEAT.relatedMode))
    assert {(b, a) for a, b in pairs} == pairs


def test_typically_exhibits_not_along_hierarchy(g):
    for a, b in g.subject_objects(CAVEAT.typicallyExhibits):
        assert b not in ancestors(g, a) and a not in ancestors(g, b), \
            f"{local(a)} typicallyExhibits {local(b)} restates parentage"


# --------------------------------------------------------------------------- rebuttals

def rebuttal_links(g):
    return set(g.subjects(RDF.type, CAVEAT.RebuttalLink))


def test_manifest_rows_valid():
    schema = json.loads(MANIFEST_SCHEMA.read_text())
    assert schema["properties"]["venueType"]["enum"] == SPEC["venue_types"]
    rows = manifest_rows()
    for row in rows:
        jsonschema.validate(row, schema)
        if "doi" in row:
            assert row["source"] == f"https://doi.org/{row['doi']}", row["id"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate manifest ids"


def test_rebuttal_links_match_manifest(g):
    rows = {r["id"]: r for r in manifest_rows()}
    used = set()
    for n in rebuttal_links(g):
        name = local(n)
        assert name.startswith("rebuttal_"), name
        mode_name, _, source_id = name[len("rebuttal_"):].partition("_")
        mode = one(g, n, CAVEAT.rebutsMode)
        assert local(mode) == mode_name, f"{name} does not match its mode {mode}"
        assert mode in modes(g)
        assert (one(g, n, CAVEAT.rebuttalKind), RDF.type, OWL.NamedIndividual) in g
        assert g.value(n, RDFS.label) is None
        assert source_id in rows, f"{name}: no manifest row {source_id}"
        row = rows[source_id]
        assert str(one(g, n, CAVEAT.rebuttalSource)) == row["source"]
        archived = g.value(n, CAVEAT.archivedAt)
        assert (None if archived is None else str(archived)) == row.get("archivedAt")
        used.add(source_id)
    assert used == set(rows), f"manifest rows no link uses: {sorted(set(rows) - used)}"


def test_rebutted_by_is_projection(g):
    projected = {(one(g, n, CAVEAT.rebutsMode), one(g, n, CAVEAT.rebuttalSource))
                 for n in rebuttal_links(g)}
    assert set(g.subject_objects(CAVEAT.rebuttedBy)) == projected


# --------------------------------------------------------------------------- modes.csv

@pytest.mark.parametrize("local_name, code", [
    ("ColdFusionLENR", "cold_fusion_lenr"),
    ("ESPPrecognition", "esp_precognition"),
    ("NRays", "n_rays"),
    ("PHackingHARKing", "p_hacking_harking"),
    ("COVID19Misinformation", "covid19_misinformation"),
    ("LLMConversationArticle", "llm_conversation_article"),
    ("UnreliabilityMode", "unreliability_mode"),
])
def test_finding_code(local_name, code):
    assert finding_code(local_name) == code


def test_modes_rows(g):
    rows = modes_rows(g)
    assert MODES_COLUMNS == SPEC["modes_csv_columns"]
    assert {r["mode_curie"] for r in rows} == {f"caveat:{local(m)}" for m in modes(g)}
    categories = {f"caveat:{local(c)}" for c in g.subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode)}
    codes = [r["finding_code"] for r in rows]
    assert len(codes) == len(set(codes)), "finding codes collide"
    for r in rows:
        assert set(r) == set(MODES_COLUMNS)
        assert r["category_curies"] and set(r["category_curies"].split("|")) <= categories
        parents = r["parent_curies"].split("|")
        assert parents == sorted(parents)


def test_modes_rows_multi_parent():
    """A second parent shows in parent_curies; categories come from all paths."""
    g = Graph()
    for name, parent in (("A", "UnreliabilityMode"), ("B", "UnreliabilityMode"),
                         ("X", "A"), ("Y", "B"), ("Z", "X")):
        g.add((CAVEAT[name], RDFS.subClassOf, CAVEAT[parent]))
    g.add((CAVEAT.Z, RDFS.subClassOf, CAVEAT.Y))
    row = {r["mode_curie"]: r for r in modes_rows(g)}[curie(CAVEAT.Z)]
    assert row["parent_curies"] == f"{curie(CAVEAT.X)}|{curie(CAVEAT.Y)}"
    assert row["category_curies"] == f"{curie(CAVEAT.A)}|{curie(CAVEAT.B)}"
