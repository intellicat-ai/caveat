"""Authoring helpers in scripts/authoring/, offline.

Network calls are replaced by fixtures. Tests that need the authoring
dependencies (requirements-authoring.txt) skip when they are not installed,
as in ontology CI.
"""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "authoring"))
import stats  # noqa: E402


# --------------------------------------------------------------------------- statistics

def test_wilson():
    assert stats.wilson(0, 0) == (0.0, 1.0)
    lo, hi = stats.wilson(15, 20)
    assert (round(lo, 2), round(hi, 2)) == (0.53, 0.89)
    assert stats.wilson(20, 20)[1] == 1.0
    assert stats.wilson_text(0, 50) == "0.00-0.07"


def test_lift():
    assert stats.lift(50, 100, 1000, 100000) == 50.0
    assert stats.lift(0, 0, 10, 10) == 0.0


@pytest.mark.parametrize("k, n, ok", [(5, 20, True), (5, 21, False), (4, 10, False), (20, 20, True), (0, 0, False)])
def test_typical_threshold(k, n, ok):
    assert stats.typical_candidate(k, n) is ok


@pytest.mark.parametrize("p, level", [(1.0, "domain_defining"), (0.9, "domain_defining"),
                                      (0.75, "domain_characteristic"), (0.69, None)])
def test_level_for(p, level):
    assert stats.level_for(p) == level


def test_request_schema():
    schema = json.loads((ROOT / "design" / "mode-request.schema.json").read_text())
    ok = {"slug": "demo-mode", "intent": "new_mode", "guidance": "g",
          "sources": [{"ref": "10.1/x", "role": "exemplar"}, {"ref": "https://example.org", "role": "pointer"}]}
    jsonschema.validate(ok, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok | {"sources": [{"ref": "x", "role": "witness"}]}, schema)


# --------------------------------------------------------------------------- with authoring dependencies

class FakeClient:
    """Stands in for net.Client: answers json() from a table keyed by URL prefix."""

    def __init__(self, table, config=None):
        self.table = table
        self.config = config or {"api_key": "", "rate": 100, "mailto": ""}

    def json(self, url, params=None, headers=None):
        for prefix, value in self.table.items():
            if url.startswith(prefix):
                return value(params) if callable(value) else value
        return None


@pytest.fixture
def authoring():
    pytest.importorskip("requests_cache")
    pytest.importorskip("lxml")
    import acquire
    import harvest
    import openalex
    import rebuttals
    import terms
    return {"acquire": acquire, "harvest": harvest, "openalex": openalex, "rebuttals": rebuttals, "terms": terms}


def test_phrase_filter(authoring):
    assert authoring["openalex"].phrase_filter('a "b", c') == 'title_and_abstract.search:"a  b   c"'
    assert authoring["openalex"].phrase_filter("x", "title") == 'title.search:"x"'


def test_tei_to_text(authoring):
    tei = b"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt>
      <title>A Title</title></titleStmt></fileDesc><profileDesc><abstract><p>Short abstract.</p></abstract>
      </profileDesc></teiHeader><text><body><div><p>Body   text.</p></div></body></text></TEI>"""
    assert authoring["acquire"].tei_to_text(tei) == "A Title\n\nShort abstract.\n\nBody text."


def test_verify_doi_reports_retraction(authoring):
    crossref = {"message": {"DOI": "10.1/x", "title": ["T"], "issued": {"date-parts": [[2001]]},
                            "container-title": ["J"], "updated-by": [{"type": "retraction"}]}}
    client = FakeClient({"https://api.crossref.org/works/": crossref,
                         "https://api.openalex.org/works/": {"id": "https://openalex.org/W1", "is_retracted": False}})
    rec = authoring["rebuttals"].verify_doi(client, "https://doi.org/10.1/x")
    assert rec["source"] == "https://doi.org/10.1/x" and rec["is_retracted"] is True
    assert rec["notices"] == ["retraction"] and rec["openalex_id"] == "W1"
    assert rec["kind"] is None and rec["venueType"] is None


def test_verify_doi_unresolved(authoring):
    assert authoring["rebuttals"].verify_doi(FakeClient({}), "10.1/missing")["status"] == "unresolved"


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_precision_and_harvest_summaries(authoring, tmp_path, monkeypatch):
    terms, harvest = authoring["terms"], authoring["harvest"]
    monkeypatch.setattr(terms, "ROOT", tmp_path)
    monkeypatch.setattr(harvest, "ROOT", tmp_path)
    write_jsonl(tmp_path / "work/s/probes/a.jsonl",
                [{"term": "a"}] + [{"id": f"W{i}", "label": i < 18} for i in range(20)])
    write_jsonl(tmp_path / "work/s/probes/b.jsonl", [{"term": "b"}, {"id": "W1", "label": None}])
    rows = {r["term"]: r for r in terms.precision("s")}
    assert rows["a"]["precision"] == 0.9 and rows["a"]["level"] == "domain_defining"
    assert rows["b"]["status"] == "1 of 1 unlabelled"
    write_jsonl(tmp_path / "work/s/harvest/labels.jsonl",
                [{"query": "q", "date": "2026-11-09"}]
                + [{"key": f"W{i}", "modes": ["DataLeakage"] if i < 5 else []} for i in range(20)]
                + [{"key": "W99", "modes": ["Pseudoreplication", "Pseudoreplication"]}])
    summary = {r["mode"]: r for r in harvest.summarize("s")}
    assert summary["DataLeakage"] == {"mode": "DataLeakage", "k": 5, "n": 21, "query": "q",
                                      "date": "2026-11-09", "candidate": False}
    assert summary["Pseudoreplication"]["k"] == 1
