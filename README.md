# CAVEAT — Controlled Annotation Vocabulary for Epistemic Aberration Types

CAVEAT is an OWL 2 ontology for classifying unreliable scientific literature and the markers used to detect it. It provides a structured, FMEA-inspired taxonomy of failure modes in scientific publishing, linked to observable detection markers and domain-specific vocabularies.

## Purpose

Scientific literature is increasingly polluted with unreliable publications ranging from outright fraud to methodological incompetence. CAVEAT provides a shared, machine-readable vocabulary for describing *what went wrong* and *how we know*, enabling interoperable tools for research credibility and integrity assessment.

## Structure

CAVEAT models two independent dimensions:

**Dimension 1 — Scientific Domain**: What field does the paper claim to belong to? Aligned to OpenAlex topics via SKOS mappings.

**Dimension 2 — Unreliability Modes**: What kind of failure does the paper exhibit? Organized as a concept tree with four top-level categories:

- **Deliberate Misconduct** — fabrication, falsification, plagiarism, papermills, predatory publishing
- **Premise-Level Failure** — pseudoscience, denialism
- **Interpretive Failure** — pathological science, systematic misinterpretation
- **Execution-Level Failure** — cargo cult methodology, statistical malpractice, reproducibility failures

Additionally, CAVEAT defines:

- **Detection Markers** — observable features that indicate unreliability (tortured phrases, image manipulation, impossible statistics, etc.), linked to failure modes via many-to-many evidential relationships
- **Controlled Vocabularies** — domain-specific lexicons intrinsic to each failure mode, with top-down inheritance through the tree

## Design Principles

- Grounded in BFO (Basic Formal Ontology) and IAO (Information Artifact Ontology) for interoperability
- FMEA-inspired hierarchy with graduated default severity and traceable causation
- Strict TBox/ABox separation: CAVEAT defines the schema, not a corpus
- Vocabularies inherit top-down: a child mode inherits its parent's terms and adds its own
- All classes have Aristotelian definitions (genus + differentia)
- OpenAlex topic alignment at topic level (currently ~4500 topics), including sibling relationships

## Namespace

```
@prefix caveat: <https://w3id.org/intellicat/caveat#> .
```

Persistent identifiers via [w3id.org](https://w3id.org/).

## Repository Layout

```
caveat/
├── src/ontology/          # TBox — the ontology (modules + imports)
├── vocabularies/          # Controlled vocabularies (YAML lexicons)
├── mappings/              # SKOS alignments to OpenAlex, MeSH, etc.
├── examples/              # ABox usage examples for downstream consumers
├── docs/                  # Documentation and diagrams
├── scripts/               # Import, validation, and generation tools
└── tests/                 # Automated consistency and CQ tests
```

See [SCOPE.md](SCOPE.md) for formal scope definition and [COMPETENCY_QUESTIONS.md](COMPETENCY_QUESTIONS.md) for the questions this ontology is designed to answer.

## Usage

CAVEAT is designed for reuse. Downstream projects import the ontology and use its classes to annotate documents:

```turtle
@prefix caveat: <https://w3id.org/intellicat/caveat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:some_paper a caveat:AnnotatedDocument ;
    caveat:primaryUnreliabilityMode caveat:BiofieldEnergyHealing ;
    caveat:claimedDomain caveat:oa_topic_T12345 ;
    caveat:detectionMarkerObserved caveat:PredatoryJournalIndexing ;
    dcterms:title "Some Dubious Paper" .
```

## Tools

- **Python**: [rdflib](https://rdflib.readthedocs.io/) for reading/querying
- **GUI**: [Protégé](https://protege.stanford.edu/) for browsing/editing
- **Validation**: HermiT reasoner via `scripts/validate.py`

## License

This work is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

Please see [CITATION.cff](CITATION.cff) for machine-readable citation metadata.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, issue templates, and review process.
