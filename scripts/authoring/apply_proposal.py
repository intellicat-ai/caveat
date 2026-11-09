#!/usr/bin/env python3
"""Apply a reviewed CAVEAT mode proposal.

Usage:
    python scripts/authoring/apply_proposal.py work/<slug>/proposal.yaml
        [--sources DIR] [--no-pytest] [--no-commit] [--trailer LINE ...]
    python scripts/authoring/apply_proposal.py work/<slug>/proposal.yaml --preview PATCH

--preview is for reviewers: it skips the review requirement, applies the
proposal, runs the validator, writes the resulting diff to PATCH and
restores every file. It never commits.

Deterministic: the same proposal on the same tree gives the same files.
The script refuses a proposal that is invalid, unreviewed, or that would
break the ontology, and leaves every file as it was when it refuses.

Steps:
 1. Validate the proposal against design/proposal.schema.json.
 2. Require a review: a reviewer listed in .reviewers who is not the
    annotator (see docs/review.md).
 3. Require a feature branch and a clean working tree.
 4. Check the operations against the ontology (classes exist or not as
    the operation needs, parents are modes, the top level is untouched,
    typicallyExhibits counts meet the threshold, every new inversion of
    severity has a rationale).
 5. Reject any shipped prose that shares an 8-word sequence with a source
    text under --sources (default work/<slug>/sources/).
 6. Write: class blocks in unreliability-modes.ttl (inserted after the
    primary parent's subtree, or replaced in place), rebuttal links in
    mode-rebuttals.ttl, lexicon files, mode-domains.csv rows, rebuttal
    manifest rows, the severity tables in docs/severity-defaults.md,
    CHANGELOG.md lines, and the committed record design/proposals/<slug>.yaml.
 7. Verify: each Turtle file changed by exactly the intended triples;
    scripts/validate.py, scripts/check_reviewed.py and (unless --no-pytest)
    the test suite pass.
 8. Commit the touched files on the current branch (unless --no-commit).
    Never pushes.
"""
import argparse
import copy
import csv
import difflib
import io
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import jsonschema
import yaml
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import turtle_edit as te  # noqa: E402
from check_reviewed import check_pair, load_reviewers  # noqa: E402

CAVEAT = te.CAVEAT
OPENALEX = "https://w3id.org/intellicat/caveat/modules/openalex#"
MODES_TTL = Path("src/ontology/modules/unreliability-modes.ttl")
REBUTTALS_TTL = Path("src/ontology/modules/mode-rebuttals.ttl")
MODE_DOMAINS = Path("mappings/openalex/mode-domains.csv")
MANIFEST = Path("mappings/rebuttals/manifest.jsonl")
SEVERITY_DOC = Path("docs/severity-defaults.md")
CHANGELOG = Path("CHANGELOG.md")
RECORDS = Path("design/proposals")
SCHEMA = Path("design/proposal.schema.json")
TYPICAL_MIN_K, TYPICAL_MIN_SHARE = 5, Decimal("0.25")
SHINGLE = 8
NOT_RECORDED = "Not yet recorded."
TERM_KEYS = ["term", "classification", "level", "general_frequency", "variants", "context_required", "rationale"]


class Refused(Exception):
    pass


# --------------------------------------------------------------------------- loading and checks

def load_proposal(root: Path, path: Path) -> dict:
    prop = yaml.safe_load(path.read_text())
    schema = json.loads((root / SCHEMA).read_text())
    try:
        jsonschema.validate(prop, schema)
    except jsonschema.ValidationError as e:
        raise Refused(f"proposal does not match {SCHEMA}: {e.message} at {list(e.absolute_path)}")
    return prop


def require_review(root: Path, prop: dict) -> None:
    ann = prop["annotation"]
    errors = check_pair("proposal", ann.get("annotator"), ann.get("reviewer"), load_reviewers(root))
    if errors:
        raise Refused(errors[0])


def git(root: Path, *args) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def require_clean_branch(root: Path) -> None:
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in ("main", "develop", "HEAD"):
        raise Refused(f"on '{branch}'; apply proposals on a feature branch")
    if git(root, "status", "--porcelain").strip():
        raise Refused("working tree has uncommitted changes")


def merged_graph(root: Path) -> Graph:
    g = Graph()
    for f in sorted((root / "src" / "ontology").rglob("*.ttl")):
        g.parse(f, format="turtle")
    return g


def modes_in(g: Graph) -> set:
    return set(g.transitive_subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode)) - {CAVEAT.UnreliabilityMode}


def categories_in(g: Graph) -> set:
    return set(g.subjects(RDFS.subClassOf, CAVEAT.UnreliabilityMode))


def check_operations(prop: dict, g: Graph) -> None:
    decision = prop["decision"]
    classes = prop.get("classes", [])
    if decision == "reject" and any(prop.get(k) for k in ("classes", "lexicons", "domains", "rebuttals")):
        raise Refused("a rejected proposal changes nothing; remove classes, lexicons, domains and rebuttals")
    creates = [c for c in classes if c["op"] == "create"]
    if decision in ("lexicon_only", "alias"):
        if creates or any("parents" in c for c in classes):
            raise Refused(f"decision {decision} may not create classes or change parents")
    if decision == "new_mode" and not creates:
        raise Refused("decision new_mode needs at least one create operation")

    modes = modes_in(g)
    categories = categories_in(g)
    for c in classes:
        cls = CAVEAT[c["name"]]
        if c["op"] == "create":
            if (cls, RDF.type, OWL.Class) in g:
                raise Refused(f"{c['name']} already exists")
            for key in ("parents", "label", "definition", "default_severity", "placement"):
                if key not in c:
                    raise Refused(f"create {c['name']}: '{key}' is required")
        else:
            if cls not in modes:
                raise Refused(f"update {c['name']}: no such unreliability mode")
            if "parents" in c and not c.get("placement"):
                raise Refused(f"update {c['name']}: a parent change needs 'placement'")
            if "parents" in c and cls in categories:
                raise Refused(f"{c['name']} is a top-level category; R1 fixes the top level")
        for p in c.get("parents", []):
            if p == "UnreliabilityMode":
                raise Refused(f"{c['name']}: R1 fixes the top level; no new direct children of UnreliabilityMode")
            if CAVEAT[p] not in modes and not any(o["name"] == p and o["op"] == "create" for o in classes):
                raise Refused(f"{c['name']}: parent {p} is not an unreliability mode")
        for t in c.get("typically_exhibits", []):
            if t["k"] > t["n"] or t["k"] < TYPICAL_MIN_K or Decimal(t["k"]) / Decimal(t["n"]) < TYPICAL_MIN_SHARE:
                raise Refused(f"{c['name']} typicallyExhibits {t['mode']}: {t['k']} of {t['n']} is below "
                              f"the threshold ({TYPICAL_MIN_K} works and 25%)")
        for other in c.get("related_modes", []) + [t["mode"] for t in c.get("typically_exhibits", [])]:
            if CAVEAT[other] not in modes and not any(o["name"] == other for o in creates):
                raise Refused(f"{c['name']}: related mode {other} does not exist")
    for r in prop.get("rebuttals", []):
        if "doi" in r and r["source"] != f"https://doi.org/{r['doi']}":
            raise Refused(f"rebuttal {r['id']}: source must be https://doi.org/{r['doi']}")
        if "doi" not in r and "archivedAt" not in r:
            raise Refused(f"rebuttal {r['id']}: a source without a DOI needs archivedAt")
        if "doi" in r and "is_retracted" not in r:
            raise Refused(f"rebuttal {r['id']}: record is_retracted for the DOI")


# --------------------------------------------------------------------------- overlap

def words(text: str) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def shingles(text: str) -> set:
    w = words(text)
    return {tuple(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}


def shipped_prose(prop: dict) -> list[tuple[str, str]]:
    """(field, text) for every prose string the proposal ships. Titles and
    citations are bibliographic, and search queries in checks are recorded
    verbatim; neither is checked."""
    out = [("summary", prop["summary"])]
    for c in prop.get("classes", []):
        for k in ("definition", "comment", "severity_rationale"):
            if k in c:
                out.append((f"{c['name']}.{k}", c[k]))
        for i, p in enumerate(c.get("placement", [])):
            out.append((f"{c['name']}.placement[{i}]", p["note"]))

        def walk(prefix, v):
            if isinstance(v, str):
                out.append((prefix, v))
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    if k2 == "query" or k2.endswith("_query"):
                        continue
                    walk(f"{prefix}.{k2}", v2)
            elif isinstance(v, list):
                for i2, v2 in enumerate(v):
                    walk(f"{prefix}[{i2}]", v2)
        walk(f"{c['name']}.checks", c.get("checks", {}))
    for lex in prop.get("lexicons", []):
        for t in lex["terms"]:
            if "rationale" in t:
                out.append((f"{lex['file']}:{t['term']}.rationale", t["rationale"]))
    for r in prop.get("rebuttals", []):
        if "scope" in r:
            out.append((f"rebuttal {r['id']}.scope", r["scope"]))
    return out


def check_overlap(prop: dict, sources_dir: Path) -> None:
    if not sources_dir.is_dir():
        return
    seen = set()
    for f in sorted(sources_dir.rglob("*")):
        if f.is_file():
            seen |= shingles(f.read_text(errors="replace"))
    for field, text in shipped_prose(prop):
        common = shingles(text) & seen
        if common:
            raise Refused(f"{field} shares an {SHINGLE}-word sequence with a source text: "
                          f"'{' '.join(sorted(common)[0])}'")


# --------------------------------------------------------------------------- ontology edits

def literal_source(value: str):
    return URIRef(value) if re.match(r"^https?://", value) else Literal(value)


def class_triples(c: dict) -> tuple[set, set]:
    """(added triples, replaced predicates) for one class operation. The
    old values of a replaced predicate are removed."""
    cls = CAVEAT[c["name"]]
    added, replace = set(), set()
    if c["op"] == "create":
        added.add((cls, RDF.type, OWL.Class))
    if "parents" in c:
        replace.add(RDFS.subClassOf)
        added |= {(cls, RDFS.subClassOf, CAVEAT[p]) for p in c["parents"]}
    simple = [("label", RDFS.label, lambda v: Literal(v, lang="en")),
              ("definition", CAVEAT.definition, lambda v: Literal(v, lang="en")),
              ("definition_source", CAVEAT.definitionSource, literal_source),
              ("comment", RDFS.comment, lambda v: Literal(v, lang="en")),
              ("default_severity", CAVEAT.defaultSeverity, lambda v: Literal(v, datatype=XSD.decimal)),
              ("lexicon_file", CAVEAT.lexiconFile, Literal)]
    for key, pred, make in simple:
        if key in c:
            replace.add(pred)
            added.add((cls, pred, make(c[key])))
    for other in c.get("related_modes", []):
        added.add((cls, CAVEAT.relatedMode, CAVEAT[other]))
    for t in c.get("typically_exhibits", []):
        added.add((cls, CAVEAT.typicallyExhibits, CAVEAT[t["mode"]]))
    return added, replace


def plan_modes(prop: dict, text: str) -> tuple[set, set]:
    """All triples the proposal adds to and removes from the modes file."""
    g = te.parse(text)
    added, removed = set(), set()
    for c in prop.get("classes", []):
        cls = CAVEAT[c["name"]]
        a, replace = class_triples(c)
        for pred in replace:
            removed |= {t for t in g.triples((cls, pred, None))}
        added |= a
        for other in c.get("related_modes", []):
            added.add((CAVEAT[other], CAVEAT.relatedMode, cls))
    for d in prop.get("domains", []):
        pred = CAVEAT.dedicatedDomain if d["kind"] == "dedicated" else CAVEAT.hostDomain
        added.add((CAVEAT[d["mode"]], pred, URIRef(OPENALEX + d["topic"].split(":", 1)[1])))
    removed -= added
    return added, removed


def apply_modes(prop: dict, text: str) -> str:
    added, removed = plan_modes(prop, text)
    before = text
    pre = te.prefix_block(text)
    created = [CAVEAT[c["name"]] for c in prop.get("classes", []) if c["op"] == "create"]
    touched = []
    for s, _, _ in sorted(added | removed):
        if s not in touched:
            touched.append(s)
    # created classes first, in proposal order, so children can follow their new parents
    order = created + [s for s in touched if s not in created]
    for cls in order:
        target = Graph()
        st = te.class_block(text, cls)
        if st is not None:
            for t in te.parse(pre + st.text):
                target.add(t)
        for t in removed:
            if t[0] == cls:
                target.remove(t)
        for t in added:
            if t[0] == cls:
                target.add(t)
        block = te.render_class(cls, target, pre)
        if st is not None:
            text = te.replace_statement(text, st, block)
            continue
        g = te.parse(text)
        primary = CAVEAT[next(c for c in prop["classes"] if CAVEAT[c["name"]] == cls)["parents"][0]]
        subtree = set(g.transitive_subjects(RDFS.subClassOf, primary))
        anchor = te.last_statement_in(text, subtree)
        text = te.insert_after(text, anchor, block)
    te.expect_delta(before, text, added, removed)
    return text


def apply_rebuttals(prop: dict, text: str) -> str:
    before = text
    pre = te.prefix_block(text)
    added = set()
    for r in sorted(prop.get("rebuttals", []), key=lambda r: (r["mode"], r["id"])):
        node = CAVEAT[f"rebuttal_{r['mode']}_{r['id']}"]
        mode, src = CAVEAT[r["mode"]], URIRef(r["source"])
        link = {(node, RDF.type, OWL.NamedIndividual), (node, RDF.type, CAVEAT.RebuttalLink),
                (node, CAVEAT.rebutsMode, mode), (node, CAVEAT.rebuttalSource, src),
                (node, CAVEAT.rebuttalKind, CAVEAT[r["kind"]])}
        if "scope" in r:
            link.add((node, CAVEAT.rebuttalScope, Literal(r["scope"])))
        if "archivedAt" in r:
            link.add((node, CAVEAT.archivedAt, URIRef(r["archivedAt"])))
        g = Graph()
        for t in link:
            g.add(t)
        text = te.append(text, te.render_statement(node, g, pre))
        text += f"{mode.n3(te.parse(pre).namespace_manager)} caveat:rebuttedBy <{src}> .\n"
        added |= link | {(mode, CAVEAT.rebuttedBy, src)}
    te.expect_delta(before, text, added, set())
    return text


# --------------------------------------------------------------------------- records

def ann(prop: dict) -> dict:
    return {"annotator": prop["annotation"]["annotator"], "reviewer": prop["annotation"]["reviewer"]}


def append_manifest(prop: dict, text: str) -> str:
    rows = {json.loads(l)["id"]: json.loads(l) for l in text.splitlines() if l.strip()}
    out = text
    for r in prop.get("rebuttals", []):
        row = {k: r[k] for k in ("id", "source", "doi", "is_retracted", "archivedAt", "openalex_id",
                                  "title", "year", "venueType", "retrieved") if k in r}
        row |= ann(prop)
        if r["id"] in rows:
            old = {k: v for k, v in rows[r["id"]].items() if k not in ("annotator", "reviewer")}
            new = {k: v for k, v in row.items() if k not in ("annotator", "reviewer")}
            if old != new:
                raise Refused(f"manifest id {r['id']} exists with different metadata")
            continue
        rows[r["id"]] = row
        out += json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    return out


def append_mode_domains(prop: dict, text: str) -> str:
    header = next(csv.reader(io.StringIO(text)))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
    for d in prop.get("domains", []):
        row = {k: "" for k in header}
        for k, v in d.items():
            if k == "mode":
                v = f"caveat:{v}"
            row[k] = "|".join(v) if isinstance(v, list) else v
        row |= ann(prop)
        w.writerow(row)
    return text + buf.getvalue()


def render_term(t: dict) -> str:
    keys = [k for k in TERM_KEYS if k in t] + sorted(k for k in t if k not in TERM_KEYS)
    lines = []
    for i, k in enumerate(keys):
        v = t[k]
        lead = "  - " if i == 0 else "    "
        lines.append(f"{lead}{k}: {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def set_annotation(text: str, a: dict) -> str:
    pat = re.compile(r'^annotation:\n  annotator: .*\n  reviewer: .*\n', re.M)
    new = f'annotation:\n  annotator: {json.dumps(a["annotator"])}\n  reviewer: {json.dumps(a["reviewer"])}\n'
    if not pat.search(text):
        raise Refused("lexicon file has no annotation block in the expected form")
    return pat.sub(lambda m: new, text, count=1)


def write_lexicon(prop: dict, lex: dict, existing: str | None) -> str:
    a = ann(prop)
    if existing is not None:
        data = yaml.safe_load(existing)
        have = {s.casefold() for t in data.get("terms", []) for s in [t["term"]] + t.get("variants", [])}
        for t in lex["terms"]:
            for s in [t["term"]] + t.get("variants", []):
                if s.casefold() in have:
                    raise Refused(f"{lex['file']}: '{s}' is already in the lexicon")
        text = set_annotation(existing, a)
        if not text.endswith("\n"):
            text += "\n"
        return text + "\n" + "\n".join(render_term(t) for t in lex["terms"])
    for key in ("domain", "inherits_from", "extraction_method"):
        if key not in lex:
            raise Refused(f"new lexicon {lex['file']}: '{key}' is required")
    em = yaml.safe_dump(lex["extraction_method"], sort_keys=False, allow_unicode=True, width=1000)
    em = "".join("  " + l for l in em.splitlines(keepends=True))
    return (f"# Generated by scripts/authoring/apply_proposal.py from design/proposals/{prop['slug']}.yaml\n"
            f"---\n"
            f"domain: {json.dumps(lex['domain'])}\n"
            f"inherits_from: {json.dumps(lex['inherits_from'])}\n"
            f"annotation:\n  annotator: {json.dumps(a['annotator'])}\n  reviewer: {json.dumps(a['reviewer'])}\n"
            f"extraction_method:\n{em}\n"
            f"terms:\n" + "\n".join(render_term(t) for t in lex["terms"]))


def committed_record(prop: dict) -> dict:
    rec = copy.deepcopy(prop)
    rec.pop("guidance", None)
    rec.pop("probes", None)
    kept = []
    for s in rec.get("sources", []):
        if s["role"] in ("pointer", "counter_exemplar"):
            continue
        if s["role"] == "exemplar" and not (s.get("prior_record") and s.get("archivedAt")):
            continue
        kept.append(s)
    if "sources" in rec:
        rec["sources"] = kept
    return rec


# --------------------------------------------------------------------------- severity tables

def severity_pairs(g: Graph) -> tuple[list, list]:
    """(below, above): (class, parent) pairs whose severities differ."""
    below, above = [], []
    for c in sorted(modes_in(g), key=str):
        sc = g.value(c, CAVEAT.defaultSeverity)
        for p in sorted(g.objects(c, RDFS.subClassOf), key=str):
            sp = g.value(p, CAVEAT.defaultSeverity)
            if sc is None or sp is None:
                continue
            if Decimal(str(sc)) < Decimal(str(sp)):
                below.append((c, p))
            elif Decimal(str(sc)) > Decimal(str(sp)):
                above.append((c, p))
    return below, above


TABLE_ROW = re.compile(r"^\| `(\w+)` \| ([\d.]+) \| `(\w+)` \| ([\d.]+) \|(?: (.*) \|)?$")


def table_span(lines: list[str], heading: str) -> tuple[int, int]:
    """Line range [first row, end) of the table under a ### heading."""
    if heading not in lines:
        raise Refused(f"{SEVERITY_DOC} has no '{heading}' table")
    h = lines.index(heading)
    i = h + 1
    while not lines[i].startswith("|"):
        i += 1
    start = i + 2
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return start, end


def update_table(lines, heading, pairs, g, rationale_for):
    start, end = table_span(lines, heading)
    want = {(te.local(c), te.local(p)) for c, p in pairs}
    sev = lambda n: str(g.value(CAVEAT[n], CAVEAT.defaultSeverity))
    rows, seen = [], set()
    for line in lines[start:end]:
        m = TABLE_ROW.match(line)
        key = (m.group(1), m.group(3))
        if key in want:
            seen.add(key)
            rows.append((key, m.group(5)))
    for c, p in pairs:
        key = (te.local(c), te.local(p))
        if key not in seen:
            rows.append((key, None))
    out = []
    for (c, p), why in rows:
        row = f"| `{c}` | {sev(c)} | `{p}` | {sev(p)} |"
        if rationale_for is not None:
            row += f" {rationale_for(c, p, why)} |"
        out.append(row)
    lines[start:end] = out


def apply_severity_doc(prop: dict, text: str, g: Graph) -> str:
    below, above = severity_pairs(g)
    rationales = {c["name"]: c["severity_rationale"] for c in prop.get("classes", []) if "severity_rationale" in c}

    def rationale_for(c, p, existing):
        # A rationale in the proposal replaces the recorded one; a new
        # inversion without one is refused.
        if c in rationales:
            return rationales[c]
        if existing is not None:
            return existing
        raise Refused(f"`{c}` is now above its parent `{p}`; give {c} a severity_rationale")

    lines = text.split("\n")
    update_table(lines, "### Classes below their parent", below, g, None)
    update_table(lines, "### Classes above their parent", above, g, rationale_for)
    return "\n".join(lines)


# --------------------------------------------------------------------------- other docs tables

DOC_TABLE_FIRST = {"Category", "Class", "Mode", "Family"}


def doc_files(root: Path) -> list[Path]:
    files = [Path("README.md")] + sorted(p.relative_to(root) for p in (root / "docs").glob("*.md"))
    return [f for f in files if f != SEVERITY_DOC and (root / f).exists()]


def refresh_doc_tables(text: str, g: Graph) -> str:
    """Bring Subclasses and Default severity cells of class tables up to date.
    Listed subclasses keep their order; new ones are appended."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) - 1:
        if not (lines[i].startswith("|") and re.match(r"^\|[\s:|-]+\|$", lines[i + 1])):
            i += 1
            continue
        header = [c.strip() for c in lines[i].strip("|").split("|")]
        j = i + 2
        while j < len(lines) and lines[j].startswith("|"):
            if header[0] in DOC_TABLE_FIRST and ("Subclasses" in header or "Default severity" in header):
                cells = [c.strip() for c in lines[j].strip("|").split("|")]
                name = re.findall(r"`([^`]+)`", cells[0])
                if len(name) == 1:
                    cls = CAVEAT[name[0]]
                    if "Subclasses" in header:
                        k = header.index("Subclasses")
                        kids = {te.local(c) for c in g.subjects(RDFS.subClassOf, cls) if str(c).startswith(str(CAVEAT))}
                        listed = [n for n in re.findall(r"`([^`]+)`", cells[k]) if n in kids]
                        listed += sorted(kids - set(listed))
                        cells[k] = ", ".join(f"`{n}`" for n in listed)
                    if "Default severity" in header:
                        sev = g.value(cls, CAVEAT.defaultSeverity)
                        if sev is not None:
                            cells[header.index("Default severity")] = str(sev)
                    lines[j] = "| " + " | ".join(cells) + " |"
            j += 1
        i = j
    return "\n".join(lines)


# --------------------------------------------------------------------------- changelog

def changelog_lines(prop: dict, before: Graph, after: Graph) -> tuple[list, list]:
    slug = prop["slug"]
    added, changed = [], []
    tick = lambda names: ", ".join(f"`{n}`" for n in names)
    parents = lambda g, n: sorted(te.local(p) for p in g.objects(CAVEAT[n], RDFS.subClassOf))
    for c in prop.get("classes", []):
        n = c["name"]
        if c["op"] == "create":
            added.append(f"- Mode `{n}` under {tick(c['parents'])} (proposal `{slug}`)")
            continue
        if "parents" in c and parents(before, n) != parents(after, n):
            changed.append(f"- Moved `{n}`: {tick(parents(before, n))} → {tick(parents(after, n))} (proposal `{slug}`)")
        if "definition" in c and str(before.value(CAVEAT[n], CAVEAT.definition)) != c["definition"]:
            changed.append(f"- Rewrote the definition of `{n}` (proposal `{slug}`)")
        if "label" in c and str(before.value(CAVEAT[n], RDFS.label)) != c["label"]:
            changed.append(f"- Relabelled `{n}`: \"{before.value(CAVEAT[n], RDFS.label)}\" → \"{c['label']}\" (proposal `{slug}`)")
        if "default_severity" in c:
            old = before.value(CAVEAT[n], CAVEAT.defaultSeverity)
            if old is None or Decimal(str(old)) != Decimal(c["default_severity"]):
                changed.append(f"- Default severity of `{n}`: {old} → {c['default_severity']} (proposal `{slug}`)")
        if "comment" in c and str(before.value(CAVEAT[n], RDFS.comment)) != c["comment"]:
            changed.append(f"- New scope note on `{n}` (proposal `{slug}`)")
    for c in prop.get("classes", []):
        for t in c.get("typically_exhibits", []):
            added.append(f"- `{c['name']}` typically exhibits `{t['mode']}` ({t['k']} of {t['n']} sampled works; proposal `{slug}`)")
        for o in c.get("related_modes", []):
            added.append(f"- `{c['name']}` related to `{o}` (proposal `{slug}`)")
    for lex in prop.get("lexicons", []):
        added.append(f"- {len(lex['terms'])} terms in `vocabularies/{lex['file']}` (proposal `{slug}`)")
    for d in prop.get("domains", []):
        added.append(f"- `{d['mode']}` {d['kind']} domain `{d['topic']}` (proposal `{slug}`)")
    for r in prop.get("rebuttals", []):
        added.append(f"- Rebuttal link for `{r['mode']}`: {r['kind']}, {r['source']} (proposal `{slug}`)")
    return added, changed


def apply_changelog(text: str, added: list, changed: list) -> str:
    lines = text.split("\n")
    top = next(i for i, l in enumerate(lines) if l.startswith("## ["))
    if not lines[top].endswith("Unreleased"):
        raise Refused("CHANGELOG.md has no Unreleased section on top")
    end = next((i for i in range(top + 1, len(lines)) if lines[i].startswith("## [")), len(lines))
    for heading, new in (("### Added", added), ("### Changed", changed)):
        if not new:
            continue
        section = lines[top:end]
        if heading in section:
            h = top + section.index(heading)
            j = h + 1
            while j < end and not lines[j].startswith("### ") and lines[j].strip():
                j += 1
            lines[j:j] = new
        else:
            insert_at = end
            while lines[insert_at - 1].strip() == "":
                insert_at -= 1
            lines[insert_at:insert_at] = ["", heading] + new
        end = next((i for i in range(top + 1, len(lines)) if lines[i].startswith("## [")), len(lines))
    return "\n".join(lines)


# --------------------------------------------------------------------------- main

def apply(root: Path, proposal_path: Path, sources: Path | None, run_pytest: bool, commit: bool,
          trailers: list[str], preview: Path | None = None) -> list[Path]:
    prop = load_proposal(root, proposal_path)
    if preview is None:
        require_review(root, prop)
    require_clean_branch(root)
    before_g = merged_graph(root)
    check_operations(prop, before_g)
    check_overlap(prop, sources or root / "work" / prop["slug"] / "sources")

    record_path = RECORDS / f"{prop['slug']}.yaml"
    if (root / record_path).exists():
        raise Refused(f"{record_path} exists; proposal slugs are used once")

    originals: dict[Path, str | None] = {}

    def write(rel: Path, text: str):
        p = root / rel
        if p.exists() and p.read_text() == text:
            return
        if rel not in originals:
            originals[rel] = p.read_text() if p.exists() else None
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(rel: Path) -> str | None:
        p = root / rel
        return p.read_text() if p.exists() else None

    try:
        if prop.get("classes") or prop.get("domains"):
            write(MODES_TTL, apply_modes(prop, read(MODES_TTL)))
        if prop.get("rebuttals"):
            write(REBUTTALS_TTL, apply_rebuttals(prop, read(REBUTTALS_TTL)))
            write(MANIFEST, append_manifest(prop, read(MANIFEST) or ""))
        if prop.get("domains"):
            write(MODE_DOMAINS, append_mode_domains(prop, read(MODE_DOMAINS)))
        for lex in prop.get("lexicons", []):
            rel = Path("vocabularies") / lex["file"]
            write(rel, write_lexicon(prop, lex, read(rel)))
        for c in prop.get("classes", []):
            if c["op"] == "update" and "parents" in c:
                lexfile = before_g.value(CAVEAT[c["name"]], CAVEAT.lexiconFile)
                if lexfile is not None:
                    rel = Path("vocabularies") / str(lexfile)
                    text = read(rel)
                    new = re.sub(r'^inherits_from: .*$', f'inherits_from: "caveat:{c["parents"][0]}"',
                                 text, count=1, flags=re.M)
                    if new != text:
                        write(rel, set_annotation(new, ann(prop)))
        after_g = merged_graph(root)
        write(SEVERITY_DOC, apply_severity_doc(prop, read(SEVERITY_DOC), after_g))
        for rel in doc_files(root):
            old = read(rel)
            new = refresh_doc_tables(old, after_g)
            if new != old:
                write(rel, new)
        added, changed = changelog_lines(prop, before_g, after_g)
        if added or changed:
            write(CHANGELOG, apply_changelog(read(CHANGELOG), added, changed))
        write(record_path, "# Reviewed proposal, applied by scripts/authoring/apply_proposal.py.\n"
                           + yaml.safe_dump(committed_record(prop), sort_keys=False, allow_unicode=True, width=100))

        new_lex = {lex["file"] for lex in prop.get("lexicons", []) if originals.get(Path("vocabularies") / lex["file"]) is None}
        referenced = {str(o) for o in after_g.objects(None, CAVEAT.lexiconFile)}
        if new_lex - referenced:
            raise Refused(f"new lexicon files no class references: {sorted(new_lex - referenced)}")

        checks = [[sys.executable, "scripts/validate.py"]]
        if preview is None:
            checks.append([sys.executable, "scripts/check_reviewed.py"])
        if run_pytest and preview is None:
            checks.append([sys.executable, "-m", "pytest", "tests/", "-q"])
        for cmd in checks:
            r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
            if r.returncode != 0:
                raise Refused(f"{' '.join(cmd[1:])} failed after applying:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    except Exception:
        restore(root, originals)
        raise

    touched = sorted(originals)
    if preview is not None:
        patch = []
        for rel in touched:
            old, new = originals[rel], (root / rel).read_text()
            patch += difflib.unified_diff((old or "").splitlines(keepends=True), new.splitlines(keepends=True),
                                          f"a/{rel}" if old is not None else "/dev/null", f"b/{rel}")
        restore(root, originals)
        preview.write_text("".join(patch))
        return touched
    if commit:
        git(root, "add", "--", *map(str, touched))
        msg = f"{prop['decision']}: {prop['slug']}\n\n{prop['summary'].strip()}\n"
        if trailers:
            msg += "\n" + "\n".join(trailers) + "\n"
        subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=root, input=msg, text=True, check=True)
    return touched


def restore(root: Path, originals: dict) -> None:
    for rel, text in originals.items():
        if text is None:
            (root / rel).unlink(missing_ok=True)
        else:
            (root / rel).write_text(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("proposal", type=Path)
    ap.add_argument("--root", type=Path, default=HERE.parent.parent)
    ap.add_argument("--sources", type=Path, help="source texts for the overlap check")
    ap.add_argument("--no-pytest", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--trailer", action="append", default=[])
    ap.add_argument("--preview", type=Path, help="write the diff here, restore everything, never commit")
    a = ap.parse_args(argv)
    try:
        touched = apply(a.root.resolve(), a.proposal.resolve(), a.sources, not a.no_pytest,
                        not a.no_commit and a.preview is None, a.trailer, a.preview)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    for p in touched:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
