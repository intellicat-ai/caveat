"""Check that README.md and docs/*.md agree with the ontology.

Rules
-----
1. Every ``caveat:Name`` token must be declared in the ontology.
2. Every backticked CamelCase token (e.g. `PapermillOperation`) must be a
   CAVEAT class.
3. Inline "`Class` (default 0.3)" and "`Class` ... its default 0.3" must
   match caveat:defaultSeverity.
4. Markdown tables are checked by column header:
     Category / Class / Mode / Family  first column, one backticked class
     Default severity                  == caveat:defaultSeverity
     Cause                             == caveat:causation
     Subclasses                        == exact set of direct subclasses
     Examples                          subset of direct subclasses
     Parent                            == direct CAVEAT superclass
     Parent default severity           == parent's caveat:defaultSeverity
     Lexicon file                      == caveat:lexiconFile
   and some tables must be complete:
     Category + Default severity       all direct children of UnreliabilityMode
     Family                            all direct children of DetectionMarker
     Mode + Lexicon file               all classes with caveat:lexiconFile
     Class + Parent default severity   all classes below their parent

Write docs in these shapes and the facts are enforced. Write them any other
way and they are not.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")
REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = REPO_ROOT / "src" / "ontology"
DOC_FILES = (
    [REPO_ROOT / "README.md"]
    + sorted(p for p in (REPO_ROOT / "docs").glob("*.md"))
    + [REPO_ROOT / "docs" / "index.html"]
)

CURIE = re.compile(r"\bcaveat:([A-Za-z_]\w*)")
CAMEL = re.compile(
    r"(?:`|<code>)([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+)(?:`|</code>)"
)
TICKED = re.compile(r"`([^`]+)`")
INLINE_DEFAULT = re.compile(
    r"`([A-Z][A-Za-z0-9]+)`[^`|]*?\bdefault (\d+(?:\.\d+)?)"
)
FIRST_COL = {"Category", "Class", "Mode", "Family"}


@pytest.fixture(scope="module")
def g():
    graph = Graph()
    for f in ONTOLOGY_DIR.rglob("*.ttl"):
        graph.parse(f, format="turtle")
    return graph


def local(u):
    return str(u).split("#", 1)[1]


def caveat_classes(g):
    return {
        local(c)
        for c in g.subjects(RDF.type, OWL.Class)
        if isinstance(c, URIRef) and str(c).startswith(str(CAVEAT))
    }


def children(g, name):
    return {
        local(c)
        for c in g.subjects(RDFS.subClassOf, CAVEAT[name])
        if str(c).startswith(str(CAVEAT))
    }


def parents(g, name):
    return sorted(
        local(p) for p in g.objects(CAVEAT[name], RDFS.subClassOf)
        if str(p).startswith(str(CAVEAT))
    )


def parent(g, name):
    ps = parents(g, name)
    return ps[0] if len(ps) == 1 else None


def severity(g, name):
    v = g.value(CAVEAT[name], CAVEAT.defaultSeverity)
    return None if v is None else Decimal(str(v))


def below_parent(g):
    out = set()
    for c in caveat_classes(g):
        p = parent(g, c)
        s, ps = severity(g, c), severity(g, p) if p else None
        if s is not None and ps is not None and s < ps:
            out.add(c)
    return out


def tables(text):
    """Yield (header, rows) for each pipe table."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            header = [c.strip() for c in lines[i].strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            yield header, rows
        else:
            i += 1


def doc_params():
    return [pytest.param(p, id=str(p.relative_to(REPO_ROOT))) for p in DOC_FILES]


@pytest.mark.parametrize("path", doc_params())
def test_curies_declared(g, path):
    declared = {local(s) for s in g.subjects() if str(s).startswith(str(CAVEAT))}
    missing = sorted(set(CURIE.findall(path.read_text())) - declared)
    assert not missing, f"undeclared caveat: terms in {path.name}: {missing}"


@pytest.mark.parametrize("path", doc_params())
def test_backticked_classes_exist(g, path):
    missing = sorted(set(CAMEL.findall(path.read_text())) - caveat_classes(g))
    assert not missing, f"unknown classes in {path.name}: {missing}"


@pytest.mark.parametrize("path", doc_params())
def test_inline_defaults(g, path):
    errors = []
    for line in path.read_text().splitlines():
        if line.startswith("|"):
            continue
        for name, val in INLINE_DEFAULT.findall(line):
            if severity(g, name) != Decimal(val):
                errors.append(f"{name}: doc says {val}, ontology says {severity(g, name)}")
    assert not errors, f"{path.name}: " + "; ".join(errors)


@pytest.mark.parametrize("path", doc_params())
def test_tables(g, path):
    errors = []
    for header, rows in tables(path.read_text()):
        if not header or header[0] not in FIRST_COL:
            continue
        cols = {h: i for i, h in enumerate(header)}
        seen = set()
        for row in rows:
            row = dict(zip(header, row))
            ticked = TICKED.findall(row[header[0]])
            if len(ticked) != 1 or ticked[0] not in caveat_classes(g):
                errors.append(f"bad class cell {row[header[0]]!r}")
                continue
            c = ticked[0]
            seen.add(c)
            if "Default severity" in cols:
                if severity(g, c) != Decimal(row["Default severity"]):
                    errors.append(f"{c} severity {row['Default severity']} != {severity(g, c)}")
            if "Cause" in cols:
                actual = str(g.value(CAVEAT[c], CAVEAT.causation))
                if row["Cause"] != actual:
                    errors.append(f"{c} cause {row['Cause']} != {actual}")
            if "Subclasses" in cols:
                listed = set(TICKED.findall(row["Subclasses"]))
                if listed != children(g, c):
                    errors.append(f"{c} subclasses {sorted(listed)} != {sorted(children(g, c))}")
            if "Examples" in cols:
                extra = set(TICKED.findall(row["Examples"])) - children(g, c)
                if extra:
                    errors.append(f"{c} examples not direct subclasses: {sorted(extra)}")
            if "Parent" in cols:
                listed = TICKED.findall(row["Parent"])
                if listed != [parent(g, c)]:
                    errors.append(f"{c} parent {listed} != {parent(g, c)}")
            if "Parent default severity" in cols:
                ps = severity(g, parent(g, c))
                if ps != Decimal(row["Parent default severity"]):
                    errors.append(f"{c} parent severity {row['Parent default severity']} != {ps}")
            if "Lexicon file" in cols:
                listed = TICKED.findall(row["Lexicon file"])
                actual = str(g.value(CAVEAT[c], CAVEAT.lexiconFile))
                if listed != [actual]:
                    errors.append(f"{c} lexicon {listed} != {actual}")

        expected = None
        if header[0] == "Category" and "Default severity" in cols:
            expected = children(g, "UnreliabilityMode")
        elif header[0] == "Family":
            expected = children(g, "DetectionMarker")
        elif header[0] == "Mode" and "Lexicon file" in cols:
            expected = {local(s) for s in g.subjects(CAVEAT.lexiconFile, None)}
        elif header[0] == "Class" and "Parent default severity" in cols:
            expected = below_parent(g)
        if expected is not None and seen != expected:
            errors.append(
                f"table {header} incomplete: missing {sorted(expected - seen)}, "
                f"extra {sorted(seen - expected)}"
            )
    assert not errors, f"{path.name}:\n  " + "\n  ".join(errors)


# Claims that were false at some point. Do not reintroduce them.
KNOWN_FALSE_CLAIMS = [
    "all classes have aristotelian",
    "traceable causation",
    "hermit",
    "oa_topic_",
    "water water",
    "has not been imported yet",
    "does not yet publish openalex",
    "alignments (not yet generated)",
]
CLAIM_FILES = (
    DOC_FILES
    + [REPO_ROOT / "docs" / "_layouts" / "default.html"]
    + sorted(ONTOLOGY_DIR.rglob("*.ttl"))
    + [REPO_ROOT / "scripts" / "validate.py", REPO_ROOT / "CITATION.cff"]
)


@pytest.mark.parametrize(
    "path", [pytest.param(p, id=str(p.relative_to(REPO_ROOT))) for p in CLAIM_FILES]
)
def test_no_known_false_claims(path):
    text = path.read_text().lower()
    found = [c for c in KNOWN_FALSE_CLAIMS if c in text]
    assert not found, f"{path.name} repeats known false claims: {found}"


def test_index_lists_every_module():
    html = (REPO_ROOT / "docs" / "index.html").read_text()
    for module in sorted((ONTOLOGY_DIR / "modules").glob("*.ttl")):
        assert f"/modules/{module.name}" in html, f"docs/index.html does not link modules/{module.name}"
