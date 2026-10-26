"""scripts/authoring/apply_proposal.py against a scratch copy of the repository."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "authoring"))
import turtle_edit as te  # noqa: E402
from apply_proposal import NOT_RECORDED, main  # noqa: E402

CAVEAT = te.CAVEAT
MODES = Path("src/ontology/modules/unreliability-modes.ttl")
COPY = ["src", "vocabularies", "mappings", "docs", "design", "scripts", "CHANGELOG.md", "README.md", ".reviewers"]


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    t = tmp_path_factory.mktemp("template")
    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, t / name, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, t / name)
    git(t, "init", "-q", "-b", "main")
    git(t, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(t, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    git(t, "switch", "-q", "-c", "feature")
    return t


@pytest.fixture
def repo(template, tmp_path):
    r = tmp_path / "repo"
    shutil.copytree(template, r, symlinks=True)
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    return r


def proposal(**over):
    p = {
        "schema": "caveat-proposal/1",
        "slug": "demo",
        "intent": "new_mode",
        "decision": "new_mode",
        "date": "2026-10-27",
        "annotation": {"annotator": "agent", "reviewer": "vr"},
        "summary": "Adds a demonstration mode.",
        "classes": [{
            "name": "DemoWaterClaims", "op": "create", "parents": ["Pseudoscience"],
            "label": "demo water claims",
            "definition": "A pseudoscience asserting demonstration properties of water.",
            "default_severity": "0.95",
            "placement": [{"rule": "R2", "note": "Advances a construct of its own."}],
        }],
    }
    p.update(over)
    return p


def run(repo, tmp_path, prop, *extra):
    path = tmp_path / "proposal.yaml"
    path.write_text(yaml.safe_dump(prop, sort_keys=False))
    return main([str(path), "--root", str(repo), "--no-pytest",
                 "--trailer", "Co-Authored-By: Test <t@t>", *extra])


def graph(repo):
    g = Graph()
    for f in (repo / "src" / "ontology").rglob("*.ttl"):
        g.parse(f, format="turtle")
    return g


def clean_and_unchanged(repo):
    return git(repo, "status", "--porcelain") == "" and git(repo, "log", "--oneline").count("\n") == 1


# --------------------------------------------------------------------------- the editing layer

def test_existing_blocks_render_identically():
    text = (ROOT / MODES).read_text()
    pre = te.prefix_block(text)
    te.check_roundtrip(text)
    for st in te.statements(text):
        g = te.parse(pre + st.text)
        cls = te.statement_subject(text, st)
        if (cls, RDF.type, OWL.Class) in g and cls != CAVEAT.UnreliabilityMode:
            assert te.render_class(cls, g, pre) == st.text, te.local(cls)


@pytest.mark.parametrize("f", sorted((ROOT / "src" / "ontology" / "modules").glob("*.ttl")), ids=lambda f: f.name)
def test_statement_split_roundtrips(f):
    te.check_roundtrip(f.read_text())


# --------------------------------------------------------------------------- applying

def test_create_mode(repo, tmp_path):
    before = (repo / MODES).read_text()
    prop = proposal(
        guidance="free text that never ships",
        probes={"term": [{"work": "W1", "label": True}]},
        classes=[dict(proposal()["classes"][0], related_modes=["MagnetizedWater"],
                      lexicon_file="engagement/demo-water.yaml")],
        lexicons=[{"file": "engagement/demo-water.yaml", "domain": "caveat:DemoWaterClaims",
                   "inherits_from": "caveat:Pseudoscience",
                   "extraction_method": {"source": "test corpus", "method": "manual", "date": "2026-10-27"},
                   "terms": [{"term": "demo water", "classification": "engagement", "level": "domain_defining",
                              "variants": ["demo-water"], "rationale": "Core term."}]}],
        sources=[{"ref": "https://example.org/pointer", "role": "pointer"},
                 {"ref": "https://doi.org/10.1/a", "role": "exemplar",
                  "prior_record": "https://example.org/critique", "archivedAt": "https://archive.example.org/c"},
                 {"ref": "https://doi.org/10.1/b", "role": "exemplar"},
                 {"ref": "https://doi.org/10.1/c", "role": "counter_exemplar"},
                 {"ref": "https://doi.org/10.1/d", "role": "definition"}],
    )
    assert run(repo, tmp_path, prop) == 0
    after = (repo / MODES).read_text()
    g = graph(repo)
    demo = CAVEAT.DemoWaterClaims
    assert (demo, RDFS.subClassOf, CAVEAT.Pseudoscience) in g
    assert (demo, CAVEAT.relatedMode, CAVEAT.MagnetizedWater) in g
    assert (CAVEAT.MagnetizedWater, CAVEAT.relatedMode, demo) in g
    assert (demo, CAVEAT.lexiconFile, Literal("engagement/demo-water.yaml")) in g

    # inserted after the last statement of the Pseudoscience subtree; nothing else moved
    statements = te.statements(after)
    subjects = [te.statement_subject(after, s) for s in statements]
    i = subjects.index(demo)
    assert subjects[i - 1] in set(g.transitive_subjects(RDFS.subClassOf, CAVEAT.Pseudoscience))
    assert subjects[i + 1] not in set(g.transitive_subjects(RDFS.subClassOf, CAVEAT.Pseudoscience))
    old_lines = [l for l in before.splitlines() if "MagnetizedWater" not in l and "caveat:lexiconFile" not in l]
    new_lines = after.splitlines()
    pos = 0
    for line in old_lines:  # every untouched line survives, in order
        pos = new_lines.index(line, pos) + 1

    lex = yaml.safe_load((repo / "vocabularies/engagement/demo-water.yaml").read_text())
    assert lex["annotation"] == {"annotator": "agent", "reviewer": "vr"}
    assert lex["terms"][0]["variants"] == ["demo-water"]

    rec = yaml.safe_load((repo / "design/proposals/demo.yaml").read_text())
    assert "guidance" not in rec and "probes" not in rec
    assert [s["ref"] for s in rec["sources"]] == ["https://doi.org/10.1/a", "https://doi.org/10.1/d"]

    log = (repo / "CHANGELOG.md").read_text()
    assert "- Mode `DemoWaterClaims` under `Pseudoscience` (proposal `demo`)" in log
    msg = git(repo, "log", "-1", "--format=%B")
    assert msg.startswith("new_mode: demo") and "Co-Authored-By: Test <t@t>" in msg
    assert git(repo, "status", "--porcelain") == ""


def test_move_keeps_block_in_place(repo, tmp_path):
    before = (repo / MODES).read_text()
    old_start = te.class_block(before, CAVEAT.MagnetizedWater).start
    old_parents = sorted(te.local(p) for p in graph(repo).objects(CAVEAT.MagnetizedWater, RDFS.subClassOf))
    prop = proposal(slug="move", intent="reclassify", decision="reclassify", classes=[{
        "name": "MagnetizedWater", "op": "update", "parents": ["UltraHighDilution"],
        "placement": [{"rule": "R3", "note": "Mechanism family."}]}])
    assert run(repo, tmp_path, prop) == 0
    after = (repo / MODES).read_text()
    assert te.class_block(after, CAVEAT.MagnetizedWater).start == old_start
    assert len(after.splitlines()) == len(before.splitlines())
    g = graph(repo)
    assert set(g.objects(CAVEAT.MagnetizedWater, RDFS.subClassOf)) == {CAVEAT.UltraHighDilution}
    old = ", ".join(f"`{p}`" for p in old_parents)
    assert f"- Moved `MagnetizedWater`: {old} → `UltraHighDilution` (proposal `move`)" in \
        (repo / "CHANGELOG.md").read_text()
    lex = yaml.safe_load((repo / "vocabularies/engagement/magnetized-water.yaml").read_text())
    assert lex["inherits_from"] == "caveat:UltraHighDilution"
    assert lex["annotation"] == {"annotator": "agent", "reviewer": "vr"}
    # MagnetizedWater (1.0) is not above its new parent UltraHighDilution (1.0), and no
    # row remains for a parent it no longer has
    doc = (repo / "docs/severity-defaults.md").read_text()
    assert "| `MagnetizedWater` |" not in doc


def test_second_parent_and_inversion_rationale(repo, tmp_path):
    prop = proposal(slug="second", intent="reclassify", decision="reclassify", classes=[{
        "name": "HomeopathicPharmacology", "op": "update", "parents": ["Parapsychology", "UltraHighDilution"],
        "placement": [{"rule": "R4", "note": "Every instance is both."}]},
        {"name": "DemoWaterClaims", "op": "create", "parents": ["Denialism"], "label": "demo water claims",
         "definition": "A denialism about demonstration water.", "default_severity": "1.0",
         "severity_rationale": "Every instance asserts the impossible.",
         "placement": [{"rule": "R2", "note": "Opposes a consensus."}]}])
    assert run(repo, tmp_path, prop) == 0
    g = graph(repo)
    assert set(g.objects(CAVEAT.HomeopathicPharmacology, RDFS.subClassOf)) == {
        CAVEAT.Parapsychology, CAVEAT.UltraHighDilution}
    doc = (repo / "docs/severity-defaults.md").read_text()
    assert "| `DemoWaterClaims` | 1.0 | `Denialism` | 0.9 | Every instance asserts the impossible. |" in doc
    # a recorded row the proposal does not touch keeps its rationale
    assert f"| `CompromisedPeerReview` | 0.7 | `PublicationProcessMisconduct` | 0.6 | {NOT_RECORDED} |" in doc


def test_domains_and_rebuttals(repo, tmp_path):
    prop = proposal(slug="links", intent="extend_mode", decision="lexicon_only", classes=[],
                    domains=[{"mode": "VitalistEnergyMedicine", "topic": "caveatoa:T13044", "kind": "dedicated",
                              "covered_keywords": ["Biofield", "Qigong"], "uncovered_keywords": ["Biophoton"],
                              "seed_n": 40, "share_of_seed": 0.5, "query": "q", "taxonomy_version": "2026-09-16",
                              "date": "2026-10-27"}],
                    rebuttals=[{"id": "demo_source", "mode": "NRays", "kind": "Replication",
                                "source": "https://example.org/report", "archivedAt": "https://archive.example.org/r",
                                "title": "A report", "year": 1904, "venueType": "journal",
                                "retrieved": "2026-10-27"}])
    assert run(repo, tmp_path, prop) == 0
    g = graph(repo)
    topic = URIRef("https://w3id.org/intellicat/caveat/modules/openalex#T13044")
    assert (CAVEAT.VitalistEnergyMedicine, CAVEAT.dedicatedDomain, topic) in g
    node = CAVEAT.rebuttal_NRays_demo_source
    assert (node, RDF.type, CAVEAT.RebuttalLink) in g
    assert (CAVEAT.NRays, CAVEAT.rebuttedBy, URIRef("https://example.org/report")) in g
    rows = [json.loads(line) for line in (repo / "mappings/rebuttals/manifest.jsonl").read_text().splitlines()]
    row = next(r for r in rows if r["id"] == "demo_source")
    assert row["reviewer"] == "vr" and row["annotator"] == "agent"
    csv_text = (repo / "mappings/openalex/mode-domains.csv").read_text()
    assert "caveat:VitalistEnergyMedicine,caveatoa:T13044,dedicated,Biofield|Qigong,Biophoton" in csv_text
    assert csv_text.rstrip().endswith(",agent,vr")


def test_reject_writes_record_only(repo, tmp_path):
    prop = proposal(slug="nope", decision="reject", classes=[])
    assert run(repo, tmp_path, prop) == 0
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["design/proposals/nope.yaml"]


# --------------------------------------------------------------------------- refusals

def demo_class(**over):
    return [dict(proposal()["classes"][0], **over)]


REFUSALS = {
    "unreviewed": dict(annotation={"annotator": "agent", "reviewer": ""}),
    "self_review": dict(annotation={"annotator": "vr", "reviewer": "vr"}),
    "unlisted_reviewer": dict(annotation={"annotator": "agent", "reviewer": "zz"}),
    "schema": dict(decision="maybe"),
    "exists": dict(classes=demo_class(name="Pseudoscience")),
    "top_level": dict(classes=demo_class(parents=["UnreliabilityMode"])),
    "missing_parent": dict(classes=demo_class(parents=["NoSuchMode"])),
    "reject_with_changes": dict(decision="reject"),
    "lexicon_only_creates": dict(decision="lexicon_only"),
    "weak_association": dict(classes=demo_class(typically_exhibits=[
        {"mode": "InappropriateControls", "k": 4, "n": 10, "query": "q", "date": "2026-10-27"}])),
    "inversion_without_rationale": dict(classes=demo_class(default_severity="1.0")),
    "cycle": dict(intent="reclassify", decision="reclassify", classes=[{
        "name": "Pseudoscience", "op": "update", "parents": ["MagnetizedWater"],
        "placement": [{"rule": "R2", "note": "n"}]}]),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_refusals_leave_tree_unchanged(repo, tmp_path, name):
    assert run(repo, tmp_path, proposal(**REFUSALS[name])) == 1
    assert clean_and_unchanged(repo)


def test_refuses_on_main(repo, tmp_path):
    git(repo, "switch", "-q", "main")
    assert run(repo, tmp_path, proposal()) == 1
    assert clean_and_unchanged(repo)


def test_refuses_dirty_tree(repo, tmp_path):
    (repo / "CHANGELOG.md").write_text((repo / "CHANGELOG.md").read_text() + "\nlocal edit\n")
    assert run(repo, tmp_path, proposal()) == 1


def test_refuses_overlap_with_source_text(repo, tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    summary = "Adds a mode for papers that claim water keeps a memory of what it touched."
    (sources / "paper.tei.xml").write_text(
        "<p>We show that <hi>water keeps a memory of what it touched</hi>, as papers that claim</p>")
    assert run(repo, tmp_path, proposal(summary=summary), "--sources", str(sources)) == 1
    assert clean_and_unchanged(repo)
    (sources / "paper.tei.xml").write_text("<p>Unrelated text about water and other things entirely.</p>")
    assert run(repo, tmp_path, proposal(summary=summary), "--sources", str(sources)) == 0


def test_committed_records_match_schema():
    import jsonschema
    schema = json.loads((ROOT / "design" / "proposal.schema.json").read_text())
    for f in sorted((ROOT / "design" / "proposals").glob("*.yaml")):
        jsonschema.validate(yaml.safe_load(f.read_text()), schema)


def test_preview_restores_and_needs_no_review(repo, tmp_path):
    patch = tmp_path / "demo.patch"
    prop = proposal(annotation={"annotator": "agent", "reviewer": ""})
    assert run(repo, tmp_path, prop, "--preview", str(patch)) == 0
    assert clean_and_unchanged(repo)
    text = patch.read_text()
    assert "+caveat:DemoWaterClaims a owl:Class ;" in text
    assert "+++ b/design/proposals/demo.yaml" in text


def test_docs_subclass_cells_follow(repo, tmp_path):
    prop = proposal(classes=demo_class(parents=["PremiseLevelFailure"]))
    assert run(repo, tmp_path, prop) == 0
    row = next(l for l in (repo / "README.md").read_text().splitlines() if l.startswith("| `PremiseLevelFailure` |"))
    assert row.startswith("| `PremiseLevelFailure` | premise_failure | 0.95 | `Pseudoscience`, `Denialism`")
    assert row.endswith(", `DemoWaterClaims` |")
