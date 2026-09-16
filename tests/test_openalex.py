"""OpenAlex taxonomy: fetcher, builder, committed data and TBox.

Runs offline against the committed jsonl, manifest and Turtle files.
Expected values come from design/openalex.yaml.
"""

import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import urllib.error
from collections import Counter, defaultdict
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "design" / "openalex.yaml").read_text())
OA = Namespace(SPEC["namespace"])
F = SPEC["files"]
LEVELS = ["domain", "field", "subfield", "topic"]
PARENT = {"field": "domain", "subfield": "field", "topic": "subfield"}
CLASS = {"domain": CAVEAT.OpenAlexDomain, "field": CAVEAT.OpenAlexField,
         "subfield": CAVEAT.OpenAlexSubfield, "topic": CAVEAT.OpenAlexTopic}
PARENT_PROP = {"field": CAVEAT.parentDomain, "subfield": CAVEAT.parentField,
               "topic": CAVEAT.parentSubfield}
SIB_PROP = {lv: CAVEAT[p] for lv, p in SPEC["tbox"]["sibling_properties"].items()}
ID_RE = {"domain": r"^\d+$", "field": r"^\d+$", "subfield": r"^\d+$", "topic": r"^T\d+$"}


def local(level, i):
    return OA[SPEC["local_names"][level].format(id=i)]


def load(name):
    spec = importlib.util.spec_from_file_location(f"_openalex_{name}", ROOT / F[name])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def records():
    lines = (ROOT / F["raw"]).read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines]


@pytest.fixture(scope="module")
def by_level(records):
    out = defaultdict(dict)
    for r in records:
        out[r["level"]][r["id"]] = r
    return out


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / F["manifest"]).read_text())


@pytest.fixture(scope="module")
def tax():
    return Graph().parse(ROOT / F["taxonomy_ttl"], format="turtle")


@pytest.fixture(scope="module")
def sib():
    return Graph().parse(ROOT / F["siblings_ttl"], format="turtle")


@pytest.fixture(scope="module")
def tbox():
    g = Graph()
    for f in (ROOT / "src" / "ontology").rglob("*.ttl"):
        g.parse(f, format="turtle")
    return g


def norm(s):
    return " ".join(str(s).split())


# --------------------------------------------------------------------------- TBox

def test_concept_classes(tbox):
    for c in SPEC["tbox"]["concept_classes"]:
        assert (CAVEAT[c], RDFS.subClassOf, SKOS.Concept) in tbox, c


def test_broader_properties(tbox):
    for p in SPEC["tbox"]["broader_properties"]:
        assert (CAVEAT[p], RDFS.subPropertyOf, SKOS.broader) in tbox, p


def test_sibling_properties(tbox):
    for lv, p in SIB_PROP.items():
        assert (p, RDF.type, OWL.ObjectProperty) in tbox, p
        assert (p, RDF.type, OWL.SymmetricProperty) in tbox, p
        assert (p, RDFS.subPropertyOf, SKOS.related) in tbox, p
        assert (p, RDFS.domain, CLASS[lv]) in tbox, p
        assert (p, RDFS.range, CLASS[lv]) in tbox, p


def test_new_properties(tbox):
    kinds = {"ObjectProperty": OWL.ObjectProperty, "AnnotationProperty": OWL.AnnotationProperty}
    for p in SPEC["tbox"]["new_properties"]:
        n = CAVEAT[p["id"]]
        assert (n, RDF.type, kinds[p["kind"]]) in tbox
        assert str(tbox.value(n, RDFS.label)) == p["label"]
        if "definition" in p:
            assert norm(tbox.value(n, CAVEAT.definition)) == norm(p["definition"])


def test_changed_definitions(tbox):
    for pid, text in SPEC["tbox"]["changed_definitions"].items():
        assert norm(tbox.value(CAVEAT[pid], CAVEAT.definition)) == norm(text)


# --------------------------------------------------------------------------- config and API access

def test_config_example():
    ex = ROOT / F["config_example"]
    import tomllib
    data = tomllib.loads(ex.read_text())
    section = data[SPEC["api"]["config_section"]]
    assert set(section) == set(SPEC["api"]["config_keys"])
    assert section["api_key"] == ""
    assert 0 < section["max_requests_per_second"] <= SPEC["api"]["max_rate_per_second"]


def test_config_is_gitignored():
    lines = [l.strip() for l in (ROOT / ".gitignore").read_text().splitlines()]
    assert F["config"] in lines or "/" + F["config"] in lines
    try:
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", F["config"]],
                                 capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    assert tracked.strip() == "", f"{F['config']} is tracked by git"


def test_missing_or_empty_config(tmp_path):
    mod = load("fetcher")
    with pytest.raises(SystemExit) as e:
        mod.load_config(tmp_path / "nope.toml")
    assert "openalex.example.toml" in str(e.value)
    empty = tmp_path / "openalex.toml"
    empty.write_text('[openalex]\napi_key = ""\n')
    mod.ensure_ignored = lambda p: None
    with pytest.raises(SystemExit) as e:
        mod.load_config(empty)
    assert "api_key" in str(e.value)


def test_key_only_in_header():
    mod = load("fetcher")
    h = mod.request_headers("SECRET123")
    assert h["Authorization"] == "Bearer SECRET123"
    assert "User-Agent" in h
    for lv in LEVELS:
        url = mod.page_url(lv, "*")
        assert "api_key" not in url and "SECRET123" not in url
        assert f"per_page={SPEC['api']['per_page']}" in url
    assert mod.PER_PAGE == SPEC["api"]["per_page"]


def test_rate_limiter_bounds_and_pacing():
    mod = load("fetcher")
    for bad in (0, -1, SPEC["api"]["max_rate_per_second"] + 1, 100, 150):
        with pytest.raises(ValueError):
            mod.RateLimiter(bad)
    t = [0.0]
    slept = []
    lim = mod.RateLimiter(5, clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    for _ in range(3):
        lim.wait()
    assert slept == pytest.approx([0.2, 0.2])


class _Resp(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(json.dumps(body).encode())
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_retry_on_429_and_no_key_in_errors(monkeypatch):
    mod = load("fetcher")
    calls = []

    def fake_open(req, timeout=60):
        calls.append(req)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {"Retry-After": "1"}, None)
        return _Resp({"meta": {"count": 0}, "results": []}, {"X-RateLimit-Remaining": "99"})

    monkeypatch.setattr(mod, "_open", fake_open)
    lim = mod.RateLimiter(50, sleep=lambda s: None)
    data, headers = mod.get_json("https://api.openalex.org/topics?per_page=100", "SECRET123", lim,
                                 sleep=lambda s: None)
    assert len(calls) == 2
    assert all(c.get_header("Authorization") == "Bearer SECRET123" for c in calls)

    def always_403(req, timeout=60):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(mod, "_open", always_403)
    with pytest.raises(SystemExit) as e:
        mod.get_json("https://api.openalex.org/topics", "SECRET123", lim, sleep=lambda s: None)
    assert "SECRET123" not in str(e.value) and "403" in str(e.value)


# --------------------------------------------------------------------------- raw data

def test_manifest_matches_jsonl(records, manifest):
    raw = (ROOT / F["raw"]).read_bytes()
    assert manifest["jsonl_sha256"] == hashlib.sha256(raw).hexdigest()
    counts = Counter(r["level"] for r in records)
    assert manifest["counts"] == {lv: counts[lv] for lv in LEVELS}
    assert manifest["source"] in ("api", "jsonl")
    for k in ("fetched_at", "api_base", "api_meta_counts", "sibling_pairs", "dangling_siblings",
              "normalization"):
        assert k in manifest, k
    assert not set(k.lower() for k in manifest) & set(SPEC["forbidden_manifest_keys"])


def test_counts_or_declared_deviation(manifest):
    pub = SPEC["published_counts"]
    dev = {lv: [pub[lv], manifest["counts"][lv]] for lv in LEVELS if manifest["counts"][lv] != pub[lv]}
    assert manifest.get("count_deviations", {}) == dev


def test_api_meta_agrees(manifest):
    for lv in LEVELS:
        assert manifest["api_meta_counts"][lv] == manifest["counts"][lv], lv


def test_line_format_and_order(records):
    text = (ROOT / F["raw"]).read_text(encoding="utf-8")
    for line, r in zip(text.splitlines(), records):
        assert line == json.dumps(r, sort_keys=True, ensure_ascii=False)
    key = lambda r: (LEVELS.index(r["level"]), int(r["id"].lstrip("T")))
    assert records == sorted(records, key=key)


def test_record_keys(records):
    allowed = {lv: set(SPEC["record_keys"]["common"]) | set(SPEC["record_keys"].get(lv, [])) for lv in LEVELS}
    for r in records:
        assert set(r) <= allowed[r["level"]], (r["id"], set(r) - allowed[r["level"]])
        assert re.match(ID_RE[r["level"]], r["id"]), r["id"]
        assert isinstance(r["siblings"], list) and r["siblings"] == sorted(r["siblings"])
        for k, v in r.items():
            assert v not in (None, "") and (k == "siblings" or v != []), (r["id"], k)
        for k in ("alternatives", "keywords"):
            if k in r:
                assert r[k] == sorted(r[k])


def test_ids_unique(records):
    c = Counter((r["level"], r["id"]) for r in records)
    assert all(v == 1 for v in c.values())


def test_parent_integrity(by_level):
    for lv, parent in PARENT.items():
        for r in by_level[lv].values():
            assert r[parent] in by_level[parent], (lv, r["id"])
    for r in by_level["subfield"].values():
        assert by_level["field"][r["field"]]["domain"] == r["domain"]
    for r in by_level["topic"].values():
        s = by_level["subfield"][r["subfield"]]
        assert (s["field"], s["domain"]) == (r["field"], r["domain"])


def test_fixtures(by_level):
    fx = SPEC["fixtures"]
    for i, name in fx["domains"].items():
        assert by_level["domain"][i]["display_name"] == name
    for i, name in fx["topics"].items():
        assert by_level["topic"][i]["display_name"] == name
    assert set(by_level["field"]) == set(fx["fields"])
    for i, (fname, dname) in fx["fields"].items():
        f = by_level["field"][i]
        assert f["display_name"] == fname
        assert by_level["domain"][f["domain"]]["display_name"] == dname


def test_sibling_stats(by_level, manifest):
    for lv in LEVELS:
        pairs = sum(1 for r in by_level[lv].values() for s in r["siblings"] if s in by_level[lv])
        dangling = sum(1 for r in by_level[lv].values() for s in r["siblings"] if s not in by_level[lv])
        assert manifest["sibling_pairs"][lv] == pairs, lv
        assert manifest["dangling_siblings"][lv] == dangling, lv


NORM = SPEC["normalization"]
IRI_BAD = re.compile(r'[\x00-\x20"<>{}|\\^`\x7f]')


def test_normalization_block(manifest):
    n = manifest["normalization"]
    assert set(n) == set(NORM["normalization_kinds"])
    for kind, per_field in n.items():
        assert set(per_field) <= set(NORM["string_fields"]), (kind, per_field)
        assert all(isinstance(v, int) and v > 0 for v in per_field.values()), (kind, per_field)
    assert set(n["url_encoded"]) | set(n["url_dropped"]) <= set(NORM["url_fields"])


def test_values_are_normalized(records):
    for r in records:
        for k in NORM["string_fields"]:
            vals = r.get(k, [])
            for v in vals if isinstance(vals, list) else [vals]:
                assert v == v.strip() and v, (r["id"], k, v)
                assert v.lower() not in NORM["missing_tokens"], (r["id"], k, v)
        for k in NORM["url_fields"]:
            if k in r:
                assert r[k].lower().startswith(("http://", "https://")), (r["id"], k, r[k])
                assert not IRI_BAD.search(r[k]), (r["id"], k, r[k])


def test_turtle_iris_are_valid(tax, sib):
    for g in (tax, sib):
        for t in g:
            for term in t:
                if isinstance(term, URIRef):
                    assert not IRI_BAD.search(str(term)), str(term)


def test_normalize_junk():
    mod = load("fetcher")
    stats = mod.new_stats()
    raw = {
        "id": "https://openalex.org/T900009",
        "display_name": "  Junk Topic ",
        "description": "NaN",
        "keywords": ["ok", " none ", "  padded  ", "NULL"],
        "ids": {"wikipedia": " https://en.wikipedia.org/wiki/A B|C ", "wikidata": "nan"},
        "subfield": {"id": "https://openalex.org/subfields/9001"},
        "field": {"id": "https://openalex.org/fields/90"},
        "domain": {"id": "https://openalex.org/domains/9"},
        "siblings": [],
    }
    assert mod.normalize_record("topic", raw, stats) == {
        "level": "topic", "id": "T900009", "display_name": "Junk Topic",
        "keywords": ["ok", "padded"],
        "wikipedia": "https://en.wikipedia.org/wiki/A%20B%7CC",
        "subfield": "9001", "field": "90", "domain": "9", "siblings": [],
    }
    assert stats == {
        "stripped": {"display_name": 1, "keywords": 2, "wikipedia": 1},
        "missing_token": {"description": 1, "keywords": 2, "wikidata": 1},
        "url_encoded": {"wikipedia": 1},
        "url_dropped": {},
    }
    s2 = mod.new_stats()
    raw2 = dict(raw, ids={"wikidata": "Q42"})
    assert "wikidata" not in mod.normalize_record("topic", raw2, s2)
    assert s2["url_dropped"] == {"wikidata": 1}
    with pytest.raises(SystemExit):
        mod.normalize_record("topic", dict(raw, display_name=" nan "), mod.new_stats())


def test_builder_refuses_bad_iri():
    mod = load("builder")
    with pytest.raises(SystemExit):
        mod.iri("https://en.wikipedia.org/wiki/A B")
    with pytest.raises(SystemExit):
        mod.iri("NaN")
    assert mod.iri("https://en.wikipedia.org/wiki/A%20B") == "<https://en.wikipedia.org/wiki/A%20B>"


# --------------------------------------------------------------------------- Turtle

def test_ontology_header(tax, sib, manifest):
    o = URIRef(SPEC["ontology_iri"])
    assert (o, RDF.type, OWL.Ontology) in tax
    assert (o, OWL.imports, URIRef("https://w3id.org/intellicat/caveat")) in tax
    assert str(tax.value(o, CAVEAT.openAlexSnapshotDate)) == manifest["fetched_at"][:10]
    assert (o, URIRef("http://purl.org/dc/terms/license"),
            URIRef("https://creativecommons.org/publicdomain/zero/1.0/")) in tax
    s = URIRef(SPEC["siblings_ontology_iri"])
    assert (s, RDF.type, OWL.Ontology) in sib
    assert (s, OWL.imports, o) in sib

def test_scheme(tax, by_level):
    s = OA["scheme"]
    assert (s, RDF.type, SKOS.ConceptScheme) in tax
    tops = set(tax.objects(s, SKOS.hasTopConcept))
    assert tops == {local("domain", i) for i in by_level["domain"]}


def test_entities(tax, records):
    for r in records:
        lv, i = r["level"], r["id"]
        n = local(lv, i)
        assert (n, RDF.type, CLASS[lv]) in tax, n
        assert (n, RDF.type, SKOS.Concept) in tax, n
        assert (n, SKOS.inScheme, OA["scheme"]) in tax, n
        assert (n, SKOS.prefLabel, Literal(r["display_name"], lang="en")) in tax, n
        assert (n, RDFS.label, Literal(r["display_name"], lang="en")) in tax, n
        assert str(tax.value(n, SKOS.notation)) == i
        assert str(tax.value(n, CAVEAT.openAlexId)) == i
        assert (n, SKOS.exactMatch, URIRef(SPEC["openalex_iri"][lv].format(id=i))) in tax, n
        if "description" in r:
            assert (n, SKOS.scopeNote, Literal(r["description"], lang="en")) in tax
        assert {str(x) for x in tax.objects(n, SKOS.altLabel)} == set(r.get("alternatives", []))
        assert {str(x) for x in tax.objects(n, CAVEAT.openAlexKeyword)} == set(r.get("keywords", []))
        if "wikidata" in r:
            assert (n, SKOS.closeMatch, URIRef(r["wikidata"])) in tax
        if "wikipedia" in r:
            assert (n, RDFS.seeAlso, URIRef(r["wikipedia"])) in tax
        if lv == "domain":
            assert (n, SKOS.topConceptOf, OA["scheme"]) in tax
        else:
            p = local(PARENT[lv], r[PARENT[lv]])
            assert set(tax.objects(n, PARENT_PROP[lv])) == {p}
            assert set(tax.objects(n, SKOS.broader)) == {p}


def test_no_extra_subjects(tax, records):
    expected = {local(r["level"], r["id"]) for r in records} | {OA["scheme"], URIRef(SPEC["ontology_iri"])}
    assert set(s for s in tax.subjects() if isinstance(s, URIRef)) == expected


def test_siblings_exactly_as_listed(sib, by_level):
    for lv in LEVELS:
        got = {(str(s), str(o)) for s, o in sib.subject_objects(SIB_PROP[lv])}
        want = {(str(local(lv, i)), str(local(lv, j)))
                for i, r in by_level[lv].items() for j in r["siblings"] if j in by_level[lv]}
        assert got == want, lv
    allowed = set(SIB_PROP.values()) | {RDF.type, OWL.imports, RDFS.comment}
    assert set(sib.predicates()) <= allowed


# --------------------------------------------------------------------------- scripts

def test_builder_check_mode():
    mod = load("builder")
    assert mod.main(["--check"]) == 0


RAW_TOPIC = {
    "id": "https://openalex.org/T900001",
    "display_name": "Synthetic Topic",
    "description": "Synthetic description.",
    "keywords": ["b kw", "a kw"],
    "ids": {"openalex": "https://openalex.org/T900001", "wikipedia": "https://en.wikipedia.org/wiki/X"},
    "subfield": {"id": "https://openalex.org/subfields/9001", "display_name": "S"},
    "field": {"id": "https://openalex.org/fields/90", "display_name": "F"},
    "domain": {"id": "https://openalex.org/domains/9", "display_name": "D"},
    "siblings": [{"id": "https://openalex.org/T900003"}, {"id": "https://openalex.org/T900002"}],
    "works_count": 5, "cited_by_count": 7, "updated_date": "2026-01-01T00:00:00",
}
RAW_FIELD = {
    "id": "https://openalex.org/fields/90", "display_name": "F", "description": None,
    "display_name_alternatives": ["zz", "aa"],
    "ids": {"openalex": "https://openalex.org/fields/90", "wikidata": "https://www.wikidata.org/wiki/Q1", "wikipedia": None},
    "domain": {"id": "https://openalex.org/domains/9", "display_name": "D"},
    "subfields": [{"id": "https://openalex.org/subfields/9001"}],
    "siblings": [],
}


def test_fetcher_normalizes():
    mod = load("fetcher")
    assert mod.normalize_record("topic", RAW_TOPIC) == {
        "level": "topic", "id": "T900001", "display_name": "Synthetic Topic",
        "description": "Synthetic description.", "keywords": ["a kw", "b kw"],
        "wikipedia": "https://en.wikipedia.org/wiki/X",
        "subfield": "9001", "field": "90", "domain": "9",
        "siblings": ["T900002", "T900003"],
    }
    assert mod.normalize_record("field", RAW_FIELD) == {
        "level": "field", "id": "90", "display_name": "F", "alternatives": ["aa", "zz"],
        "wikidata": "https://www.wikidata.org/wiki/Q1", "domain": "9", "siblings": [],
    }


def test_release_artifact(tmp_path, tax, sib):
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_artifacts import build
    from rdflib.compare import isomorphic
    build(tmp_path)
    assert isomorphic(Graph().parse(tmp_path / F["release_taxonomy"], format="turtle"), tax)
    assert isomorphic(Graph().parse(tmp_path / F["release_siblings"], format="turtle"), sib)
    core = Graph().parse(tmp_path / "caveat-full.ttl", format="turtle")
    assert not any(str(s).startswith(SPEC["namespace"]) for s in core.subjects())

# --------------------------------------------------------------------------- docs
