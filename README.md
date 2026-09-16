# CAVEAT: Controlled Annotation Vocabulary for Epistemic Aberration Types

CAVEAT is an OWL 2 ontology for classifying unreliable scientific literature and the markers used to detect it. It provides an FMEA-inspired taxonomy of the ways a publication can fail, links those failure modes to observable detection markers, and attaches controlled vocabularies to selected modes.

Documentation site: <https://intellicat-ai.github.io/caveat/>

## Purpose

Scientific literature is increasingly polluted with unreliable publications, ranging from outright fraud to methodological incompetence. CAVEAT provides a shared, machine-readable vocabulary for describing *what went wrong* and *how we know*, enabling interoperable tools for research credibility and integrity assessment.

## Structure

CAVEAT describes a paper along two independent dimensions.

**Scientific domain.** What field does the paper claim to contribute to? CAVEAT maps the four-level OpenAlex hierarchy (domain, field, subfield, topic) to SKOS concepts under `caveatoa:` (`https://w3id.org/intellicat/caveat/modules/openalex#`), with the sibling lists OpenAlex publishes at each level. The taxonomy ships as two modules that the root ontology does not import, `modules/openalex` and `modules/openalex-siblings`; see [mappings/README.md](mappings/README.md).

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

Each marker-to-mode link is a named `caveat:EvidenceLink` node with its own `caveat:evidenceStrength`: `caveat:DefinitiveEvidence`, `caveat:StrongEvidence`, `caveat:ModerateEvidence`, `caveat:WeakEvidence`, or `caveat:GradedEvidence`, where strength is read from the intensity reported with each observation. A `caveat:StatedReasonEvidenceLink` has no fixed mode: the observed notice names it, as a retraction notice does. `caveat:evidenceFor` remains as a direct marker-to-mode shortcut for fixed links. The relation is many-to-many. Not every marker is linked to a mode yet; see [`src/ontology/modules/marker-evidence.ttl`](src/ontology/modules/marker-evidence.ttl).

**Reporting.** Pipelines that score papers can explain a score in CAVEAT terms: which mode, which marker, which detector, and with what confidence. The assessment module defines `MarkerObservation`, `ModeAssessment` and `Detector`; the `caveat-assessment/1` JSON profile carries them as plain JSON that is also JSON-LD. See [docs/reporting-profile.md](docs/reporting-profile.md).

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

- Core classes are aligned to BFO and IAO. `UnreliabilityMode` and `DetectionMarker` are BFO qualities (`BFO_0000019`); `AnnotatedDocument` is an IAO information content entity (`IAO_0000030`). Only the BFO and IAO classes CAVEAT builds on are imported, as local excerpts. Evidence links, marker observations and mode assessments are IAO information content entities, and detectors are PROV agents. The OpenAlex hierarchy classes are SKOS concepts. `CorpusFamily`, `RetractionRecord`, `EvidenceStrength` and `TopicRelation` are not aligned to an upper ontology. See [docs/bfo-alignment.md](docs/bfo-alignment.md).
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

Release artifacts are built at publish time by `scripts/build_artifacts.py` and served from the documentation site: `caveat-full.ttl` (merged Turtle), `caveat.owl` (merged RDF/XML), and the root `caveat.ttl` with its `modules/` and `imports/`.

For tooling, `caveat-full.ttl` is self-contained. The root `caveat.ttl` instead imports module IRIs under `https://w3id.org/intellicat/caveat/modules/`; tools that follow `owl:imports` need those IRIs to resolve.

## Usage

Downstream projects import the ontology and annotate documents with its classes:

```turtle
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix caveat:   <https://w3id.org/intellicat/caveat#> .
@prefix caveatoa: <https://w3id.org/intellicat/caveat/modules/openalex#> .
@prefix dcterms:  <http://purl.org/dc/terms/> .
@prefix ex:       <https://example.org/> .

<https://example.org/annotations> a owl:Ontology ;
    owl:imports <https://w3id.org/intellicat/caveat> ,
                <https://w3id.org/intellicat/caveat/modules/openalex> .

# caveatoa:T13044 is the OpenAlex topic "Biofield Effects and Biophysics".
ex:some_paper a caveat:AnnotatedDocument ;
    dcterms:title "Some Dubious Paper" ;
    caveat:primaryUnreliabilityMode caveat:BiofieldEnergyHealing ;
    caveat:detectionMarkerObserved caveat:PredatoryJournalIndexing ;
    caveat:claimedDomain caveatoa:T13044 .
```

A fuller example, with a corpus family, is in [`examples/trivedi-2016.ttl`](examples/trivedi-2016.ttl). See [SCOPE.md](SCOPE.md) for the formal scope and [COMPETENCY_QUESTIONS.md](COMPETENCY_QUESTIONS.md) for the questions CAVEAT is designed to answer.

## Repository Layout

```
caveat/
├── src/ontology/          # Ontology source: root file, modules, BFO/IAO excerpts
├── vocabularies/          # YAML lexicons, their schema, and the reporting profile (profiles/)
├── mappings/              # OpenAlex taxonomy as SKOS; see ROADMAP.md for planned alignments
├── examples/              # Example annotation and SPARQL queries
├── docs/                  # Design notes, GitHub Pages site, release artifacts
├── config/                # Local settings templates (real config files are git-ignored)
├── design/                # Specifications the tests check the ontology and tools against
├── scripts/               # Validation, vocabulary resolution, OpenAlex import, release build
└── tests/                 # pytest suite
```

## Tools

Install the development dependencies with `pip install -r requirements-dev.txt`.

- `python scripts/validate.py` runs structural checks with rdflib: parsing, labels, definitions, default severities, evidence strengths, lexicon file references and lexicon schema conformance. It does not run an OWL reasoner.
- `python scripts/resolve_vocabulary.py caveat:BiofieldEnergyHealing` prints a mode's merged, inherited vocabulary as JSON.
- `python scripts/check_curies.py . --allow .caveat-curie-allowlist` reports `caveat:` CURIEs the ontology does not declare. It also works on other repositories.
- `python scripts/fetch_openalex_taxonomy.py --source api` refreshes the OpenAlex data; `python scripts/build_openalex_mapping.py` rebuilds the Turtle from it (`--check` verifies it is current). The fetcher reads an API key from the git-ignored `config/openalex.toml`; copy `config/openalex.example.toml`.
- `python scripts/check_assessment.py FILE.json` validates `caveat-assessment/1` payloads against `vocabularies/profiles/`.
- `python scripts/build_artifacts.py OUT_DIR` builds the release artifacts into `OUT_DIR`.
- `python -m pytest tests/` runs the test suite, including release-artifact build checks and a check that this README and `docs/` match the ontology.

CI runs the validator, the CURIE check, the OpenAlex mapping and profile example checks, the test suite and a vocabulary-inheritance check on pushes and pull requests to `main` and `develop`. Planned work is listed in [ROADMAP.md](ROADMAP.md).

To browse the ontology, open `caveat-full.ttl` from the documentation site in [Protégé](https://protege.stanford.edu/). For programmatic access, use [rdflib](https://rdflib.readthedocs.io/).

## License

This work is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

CAVEAT is written by the [CAVEAT contributors](https://github.com/intellicat-ai/caveat/graphs/contributors) and maintained by Intellicat Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button generates APA and BibTeX from it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, issue templates and review process.
