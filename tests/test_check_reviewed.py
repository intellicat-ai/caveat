"""scripts/check_reviewed.py: the review gate for agent-authored records."""
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_reviewed import check  # noqa: E402


def lexicon(annotator="agent", reviewer="vr"):
    return {
        "domain": "caveat:MagnetizedWater",
        "inherits_from": "none",
        "annotation": {"annotator": annotator, "reviewer": reviewer},
        "extraction_method": {},
        "terms": [],
    }


@pytest.fixture
def root(tmp_path):
    (tmp_path / ".reviewers").write_text("# initials\nvr\nsa\n")
    (tmp_path / "vocabularies" / "engagement").mkdir(parents=True)
    (tmp_path / "vocabularies" / "_schema.yaml").write_text("title: ignored\n")
    return tmp_path


def write_lexicon(root, data, name="x.yaml"):
    (root / "vocabularies" / "engagement" / name).write_text(yaml.safe_dump(data))


def test_reviewed_lexicon_passes(root):
    write_lexicon(root, lexicon())
    assert check(root) == []


def test_reviewer_case_insensitive(root):
    write_lexicon(root, lexicon(reviewer="VR"))
    assert check(root) == []


@pytest.mark.parametrize("ann, expected", [
    ({"annotator": "agent", "reviewer": ""}, "not reviewed"),
    ({"annotator": "agent"}, "not reviewed"),
    ({"annotator": "", "reviewer": "vr"}, "annotator is empty"),
    ({"annotator": "vr", "reviewer": "vr"}, "also the annotator"),
    ({"annotator": "agent", "reviewer": "zz"}, "not listed in .reviewers"),
])
def test_bad_annotation(root, ann, expected):
    data = lexicon()
    data["annotation"] = ann
    write_lexicon(root, data)
    errors = check(root)
    assert len(errors) == 1 and expected in errors[0]


def test_missing_annotation_block(root):
    data = lexicon()
    del data["annotation"]
    write_lexicon(root, data)
    assert "missing annotation block" in check(root)[0]


def test_schema_file_skipped(root):
    assert check(root) == []


def test_missing_reviewers_file(root):
    (root / ".reviewers").unlink()
    write_lexicon(root, lexicon())
    errors = check(root)
    assert ".reviewers is missing or empty" in errors


def test_proposal_exemplars_need_prior_record(root):
    d = root / "design" / "proposals"
    d.mkdir(parents=True)
    rec = {
        "annotation": {"annotator": "agent", "reviewer": "vr"},
        "sources": [
            {"ref": "doi:10.1/a", "role": "exemplar", "prior_record": "https://example.org/a"},
            {"ref": "doi:10.1/b", "role": "exemplar"},
            {"ref": "doi:10.1/c", "role": "rebuttal"},
        ],
        "counter": {"exemplars": [{"ref": "doi:10.1/d"}]},
    }
    (d / "p.yaml").write_text(yaml.safe_dump(rec))
    errors = check(root)
    assert sorted(errors) == [
        "design/proposals/p.yaml: exemplar doi:10.1/b has no prior_record",
        "design/proposals/p.yaml: exemplar doi:10.1/d has no prior_record",
    ]


def test_rebuttal_manifest_rows(root):
    d = root / "mappings" / "rebuttals"
    d.mkdir(parents=True)
    rows = [{"annotator": "agent", "reviewer": "sa"}, {"annotator": "agent", "reviewer": ""}]
    (d / "manifest.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    errors = check(root)
    assert errors == ["mappings/rebuttals/manifest.jsonl:2: not reviewed (reviewer is empty)"]


def test_mode_domain_rows(root):
    d = root / "mappings" / "openalex"
    d.mkdir(parents=True)
    (d / "mode-domains.csv").write_text("mode,topic,annotator,reviewer\na,T1,agent,vr\nb,T2,agent,\n")
    errors = check(root)
    assert errors == ["mappings/openalex/mode-domains.csv:3: not reviewed (reviewer is empty)"]
