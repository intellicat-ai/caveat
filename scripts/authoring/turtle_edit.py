"""Edit CAVEAT Turtle modules in place, one statement at a time.

The modules are hand-formatted. These helpers never re-serialize a file:
they split it into statements, replace or insert the text of single
statements, and leave every other byte alone. Callers verify the result
with expect_delta(), which re-parses the file and checks that the graph
changed by exactly the intended triples.
"""
import re
from dataclasses import dataclass

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

CAVEAT = Namespace("https://w3id.org/intellicat/caveat#")

# Predicate order in a rendered class block. Anything else follows, sorted.
CLASS_ORDER = [
    RDFS.subClassOf, RDFS.label, CAVEAT.definition, CAVEAT.definitionSource,
    RDFS.comment, CAVEAT.defaultSeverity, CAVEAT.causation, CAVEAT.lexiconFile,
    CAVEAT.dedicatedDomain, CAVEAT.hostDomain, CAVEAT.relatedMode, CAVEAT.typicallyExhibits,
]


@dataclass
class Statement:
    start: int   # first line index (inclusive)
    end: int     # last line index (inclusive)
    text: str


def prefix_block(text: str) -> str:
    return "".join(l for l in text.splitlines(keepends=True) if l.startswith("@prefix"))


def statements(text: str) -> list[Statement]:
    """Top-level statements, in file order. Comments and blank lines between
    statements belong to none of them."""
    lines = text.splitlines(keepends=True)
    out, start, in_long = [], None, False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if not stripped or stripped.startswith("#") or stripped.startswith("@prefix"):
                continue
            start = i
        if line.count('"""') % 2 == 1:
            in_long = not in_long
        if not in_long and (stripped == "." or stripped.endswith(" .")):
            out.append(Statement(start, i, "".join(lines[start:i + 1])))
            start = None
    if start is not None:
        raise ValueError(f"unterminated statement at line {start + 1}")
    return out


def parse(text: str) -> Graph:
    g = Graph()
    g.parse(data=text, format="turtle")
    return g


def statement_subject(text: str, st: Statement) -> URIRef | None:
    subjects = set(parse(prefix_block(text) + st.text).subjects())
    return next(iter(subjects)) if len(subjects) == 1 else None


def class_block(text: str, cls: URIRef) -> Statement | None:
    """The statement that declares cls an owl:Class."""
    pre = prefix_block(text)
    for st in statements(text):
        g = parse(pre + st.text)
        if (cls, RDF.type, OWL.Class) in g:
            return st
    return None


def check_roundtrip(text: str) -> None:
    """The statements, re-joined, carry the same triples as the file."""
    whole = parse(text)
    pieces = parse(prefix_block(text) + "\n".join(s.text for s in statements(text)))
    if set(whole) != set(pieces):
        raise ValueError("statement split lost or changed triples")


def _term(g: Graph, node) -> str:
    if isinstance(node, Literal) and node.datatype == XSD.decimal:
        return f'"{node}"^^xsd:decimal'
    return node.n3(g.namespace_manager)


def render_class(cls: URIRef, triples: Graph, prefixes: str) -> str:
    """A class block in house style from the triples whose subject is cls."""
    g = Graph()
    g.parse(data=prefixes, format="turtle")
    for t in triples:
        g.add(t)
    preds = {p for p in g.predicates(cls, None) if p != RDF.type}
    order = [p for p in CLASS_ORDER if p in preds] + sorted(preds - set(CLASS_ORDER), key=str)
    lines = [f"{cls.n3(g.namespace_manager)} a owl:Class"]
    for p in order:
        objs = sorted(g.objects(cls, p), key=lambda o: _term(g, o))
        lines.append(f"    {p.n3(g.namespace_manager)} " + ", ".join(_term(g, o) for o in objs))
    return " ;\n".join(lines) + " .\n"


def render_statement(subject: URIRef, triples: Graph, prefixes: str, type_first=None) -> str:
    """A generic statement: optional rdf:type line first, then predicates sorted."""
    g = Graph()
    g.parse(data=prefixes, format="turtle")
    for t in triples:
        g.add(t)
    types = sorted(g.objects(subject, RDF.type), key=str)
    head = subject.n3(g.namespace_manager)
    if types:
        head += " a " + ", ".join(t.n3(g.namespace_manager) for t in types)
    lines = [head]
    for p in sorted({p for p in g.predicates(subject, None) if p != RDF.type}, key=str):
        objs = sorted(g.objects(subject, p), key=lambda o: _term(g, o))
        lines.append(f"    {p.n3(g.namespace_manager)} " + ", ".join(_term(g, o) for o in objs))
    if len(lines) == 1:
        raise ValueError(f"nothing to render for {subject}")
    return " ;\n".join(lines) + " .\n"


def replace_statement(text: str, st: Statement, new_text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(lines[:st.start]) + new_text + "".join(lines[st.end + 1:])


def insert_after(text: str, st: Statement, new_text: str) -> str:
    """Insert new_text as a new statement after st, separated by a blank line."""
    lines = text.splitlines(keepends=True)
    return "".join(lines[:st.end + 1]) + "\n" + new_text + "".join(lines[st.end + 1:])


def append(text: str, new_text: str) -> str:
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + new_text


def last_statement_in(text: str, subjects: set) -> Statement | None:
    """The last statement, in file order, whose subject is in subjects."""
    found = None
    for st in statements(text):
        if statement_subject(text, st) in subjects:
            found = st
    return found


def expect_delta(before: str, after: str, added: set, removed: set) -> None:
    """after parses to exactly before - removed + added."""
    b, a = set(parse(before)), set(parse(after))
    want = (b - removed) | added
    if a != want:
        extra = sorted(map(str, a - want))[:5]
        missing = sorted(map(str, want - a))[:5]
        raise ValueError(f"unexpected graph change; extra {extra}, missing {missing}")


def local(iri) -> str:
    return re.sub(r"^.*#", "", str(iri))
