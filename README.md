# CAVEAT: Controlled Annotation Vocabulary for Epistemic Aberration Types

CAVEAT is an OWL 2 ontology for classifying unreliable scientific literature and the markers used to detect it. It provides an FMEA-inspired taxonomy of the ways a publication can fail, links those failure modes to observable detection markers, and attaches controlled vocabularies to selected modes.

Documentation site: <https://intellicat-ai.github.io/caveat/>

## Purpose

Scientific literature is increasingly polluted with unreliable publications, ranging from outright fraud to methodological incompetence. CAVEAT provides a shared, machine-readable vocabulary for describing *what went wrong* and *how we know*, enabling interoperable tools for research credibility and integrity assessment.

## Structure

CAVEAT describes a paper along two independent dimensions.

**Scientific domain.** What field does the paper claim to contribute to? CAVEAT defines a schema for the four-level OpenAlex hierarchy (domain, field, subfield, topic) and for sibling relationships between topics. OpenAlex topic data has not been imported yet; see [mappings/README.md](mappings/README.md).

**Unreliability mode.** What kind of failure does the paper exhibit? Modes form a class hierarchy under `UnreliabilityMode`. Each of the four top-level categories carries a primary cause (`caveat:causation`) and a default severity (`caveat:defaultSeverity`):

| Category | Cause | Default severity | Subclasses |
|---|---|---|---|
| `DeliberateMisconduct` | intentional | 1.0 | `DataMisconduct`, `AuthorshipMisconduct`, `PublicationProcessMisconduct`, `SystematicFraudulentProduction` |
| `PremiseLevelFailure` | premise_failure | 0.95 | `Pseudoscience`, `Denialism` |
| `InterpretiveFailure` | interpretive_error | 0.6 | `PathologicalScience`, `SystematicMisinterpretation` |
| `ExecutionLevelFailure` | methodological_error | 0.3 | `DesignFailures`, `StatisticalMalpractice`, `ReproducibilityFailures`, `Overreach` |

Leaf modes include `Fabrication`, `Falsification`, `TextPlagiarism`, `PapermillOperation`, `PredatoryJournalPublication`, `CompromisedPeerReview`, `BiofieldEnergyHealing`, `HomeopathicPharmacology`, `ClimateScienceDenial`, `ColdFusionLENR`, `PHackingHARKing` and `FailedReplication`. The full tree is in [`src/ontology/modules/unreliability-modes.ttl`](src/ontology/modules/unreliability-modes.ttl).

**Detection markers.** Observable features of a publication that count as evidence for one or more modes. There are four marker families:

| Family | Examples |
|---|---|
| `TextualMarker` | `TorturedPhrases`, `VerbatimOverlap`, `LLMGeneratedText` |
| `DataFigureMarker` | `ClonedImages`, `SyntheticSpectra`, `ImpossibleStatistics` |
| `MetadataMarker` | `PredatoryJournalIndexing`, `RetractionNotice`, `CitationPatternAnomaly` |
| `ReproducibilityMarker` | `FailedIndependentReplication`, `NonResponsiveAuthors` |

Markers point to modes through `caveat:evidenceFor`, qualified by `caveat:evidenceStrength` (`definitive`, `strong`, `moderate` or `weak`). The relation is many-to-many. Not every marker is linked to a mode yet; see [`src/ontology/modules/marker-evidence.ttl`](src/ontology/modules/marker-evidence.ttl).

**Controlled vocabularies.** YAML lexicons attached to modes through `caveat:lexiconFile`. A mode's effective vocabulary is its own lexicon plus the lexicons of all its ancestors. Each term is classified as engagement, rejection or sanewashing; see [docs/term-classifications.md](docs/term-classifications.md). Lexicons currently exist for these modes:

| Mode | Lexicon file |
|---|---|
| `Pseudoscience` | `rejection/pseudoscience-base.yaml` |
| `VitalistEnergyMedicine` | `engagement/vitalist-energy-medicine.yaml` |
| `BiofieldEnergyHealing` | `engagement/biofield-energy-healing.yaml` |
| `MagnetizedWater` | `engagement/magnetized-water.yaml` |

A separate retraction-aware lexicon, `rejection/retracted-literature-base.yaml`, is attached to `UnreliabilityMode` through `caveat:retractionAwareLexiconFile`. It is not inherited. Consumers activate it per probe when the source paper has been retracted.

**Document annotation.** `AnnotatedDocument` and its properties (`caveat:primaryUnreliabilityMode`, `caveat:secondaryUnreliabilityMode`, `caveat:detectionMarkerObserved`, `caveat:claimedDomain`, `caveat:corpusFamily`) let consumers annotate papers. `CorpusFamily` groups related papers. `RetractionRecord` holds retraction date, reason, severity value and notice DOI. CAVEAT defines this schema only; annotations of specific papers are maintained by consumers.

## Design Principles

- Core classes are aligned to BFO and IAO. `UnreliabilityMode` and `DetectionMarker` are BFO qualities (`BFO_0000019`); `AnnotatedDocument` is an IAO information content entity (`IAO_0000030`). Only the BFO and IAO classes CAVEAT builds on are imported, as local excerpts. The OpenAlex hierarchy classes, `CorpusFamily` and `RetractionRecord` are not aligned to an upper ontology. See [docs/bfo-alignment.md](docs/bfo-alignment.md).
- FMEA-inspired severity. Every unreliability mode below the root has a default severity between 0.0 and 1.0. Causation is annotated on the four top-level categories. See [docs/severity-defaults.md](docs/severity-defaults.md).
- Strict TBox/ABox separation. CAVEAT defines the schema, not a corpus. The example in [`examples/`](examples/) is illustrative.
- Top-down vocabulary inheritance. A child mode inherits its ancestors' terms and adds its own. See [docs/vocabulary-inheritance.md](docs/vocabulary-inheritance.md).
- Genus-plus-differentia definitions. Every unreliability mode and detection marker has a `caveat:definition` naming its parent class and what distinguishes it. `RetractionRecord` does not have a definition yet.
- Domain classification anchors at the OpenAlex topic level, the most granular of its four levels (roughly 4,500 topics).

## Namespace

```
@prefix caveat: <https://w3id.org/intellicat/caveat#> .
```

The ontology IRI is `https://w3id.org/intellicat/caveat`. Persistent identifiers are provided by [w3id.org](https://w3id.org/). Terms use hash IRIs, so every term resolves to the ontology document.

## Getting the Ontology

The release artifacts are single, self-contained files generated from `src/ontology/` by `scripts/build_release.py`:

- [`docs/caveat.ttl`](docs/caveat.ttl) (Turtle)
- [`docs/caveat.owl`](docs/caveat.owl) (RDF/XML)

Use these for tooling. The source root, `src/ontology/caveat.ttl`, imports module IRIs that are not published individually, so tools that follow `owl:imports` will fail on it.

## Usage

Downstream projects import the ontology and annotate documents with its classes:

```turtle
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix caveat:  <https://w3id.org/intellicat/caveat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ex:      <https://example.org/> .

<https://example.org/annotations> a owl:Ontology ;
    owl:imports <https://w3id.org/intellicat/caveat> .

ex:some_paper a caveat:AnnotatedDocument ;
    dcterms:title "Some Dubious Paper" ;
    caveat:primaryUnreliabilityMode caveat:BiofieldEnergyHealing ;
    caveat:detectionMarkerObserved caveat:PredatoryJournalIndexing ;
    caveat:claimedDomain ex:topic_T12345 .

# CAVEAT does not yet publish OpenAlex topic individuals,
# so the consumer declares the topic it refers to.
ex:topic_T12345 a caveat:OpenAlexTopic ;
    caveat:openAlexId "T12345" .
```

A fuller example, with a corpus family, is in [`examples/trivedi-2016.ttl`](examples/trivedi-2016.ttl). See [SCOPE.md](SCOPE.md) for the formal scope and [COMPETENCY_QUESTIONS.md](COMPETENCY_QUESTIONS.md) for the questions CAVEAT is designed to answer.

## Repository Layout

```
caveat/
├── src/ontology/          # Ontology source: root file, modules, BFO/IAO excerpts
├── vocabularies/          # YAML lexicons and their schema
├── mappings/              # Planned SKOS alignments (not yet generated)
├── examples/              # Example annotation and SPARQL queries
├── docs/                  # Design notes, GitHub Pages site, release artifacts
├── scripts/               # Validation, vocabulary resolution, release build
└── tests/                 # pytest suite
```

## Tools

Install the development dependencies with `pip install -r requirements-dev.txt`.

- `python scripts/validate.py` runs structural checks with rdflib: parsing, labels, definitions, default severities, evidence strengths, lexicon file references and lexicon schema conformance. It does not run an OWL reasoner.
- `python scripts/resolve_vocabulary.py caveat:BiofieldEnergyHealing` prints a mode's merged, inherited vocabulary as JSON.
- `python scripts/build_release.py` regenerates `docs/caveat.ttl` and `docs/caveat.owl`. Add `--check` to verify they are current.
- `python -m pytest tests/` runs the test suite, including release-artifact freshness and a check that this README and `docs/` match the ontology.

CI runs the validator, the test suite and a vocabulary-inheritance check on pushes and pull requests to `main` and `develop`.

To browse the ontology, open `docs/caveat.ttl` in [Protégé](https://protege.stanford.edu/). For programmatic access, use [rdflib](https://rdflib.readthedocs.io/).

## License

This work is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

CAVEAT is written by the [CAVEAT contributors](https://github.com/intellicat-ai/caveat/graphs/contributors) and maintained by Intellicat Inc. Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button generates APA and BibTeX from it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, issue templates and review process.
