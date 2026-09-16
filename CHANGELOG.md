# CAVEAT Changelog

All notable changes to this ontology will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.4.0] - Unreleased

### Added
- Evidence model: `caveat:EvidenceLink` named nodes (`caveat:linkMarker`, `caveat:linkMode`, `caveat:evidenceStrength`), so each link carries its own strength
- `caveat:EvidenceStrength` value partition with individuals `DefinitiveEvidence`, `StrongEvidence`, `ModerateEvidence`, `WeakEvidence`, `GradedEvidence`; `caveat:strengthRank` and `caveat:intensityLowerBound` annotations
- `caveat:StatedReasonEvidenceLink`: links whose mode is the one named by the observed notice (retraction notices, expressions of concern)
- `scripts/check_curies.py` and `.caveat-curie-allowlist`: reports `caveat:` CURIEs the ontology does not declare; usable on consumer repositories
- Validator hierarchy check: subclass cycles, orphan classes, undeclared CAVEAT parents
- Evidence model tests (`tests/test_evidence_model.py`) against a design specification (`design/evidence-model.yaml`)
- Release artifacts built at publish time by `scripts/build_artifacts.py`: `caveat.ttl`, `caveat-full.ttl`, `caveat.owl`, `modules/`, `imports/`
- GitHub Pages documentation site in `docs/` with Jekyll configuration, responsive stylesheet, default layout, and landing page
- Test suite (`tests/test_release_artifacts.py`) verifying release artifact isomorphism and version synchronization
- Documentation consistency test (`tests/test_docs_consistency.py`) checking class names, severities, causation, subclasses, parents and lexicon paths in `README.md` and `docs/*.md` against the ontology
- `docs/index.html` added to the documentation consistency test; regression test for previously corrected false claims
- Tests for unique `rdfs:label` values, `CITATION.cff` authorship, and byte-stable release artifacts
- CI step validating `CITATION.cff` with `cffconvert`
- Citation section on the documentation site and in `README.md`

### Changed
- `caveat:evidenceStrength` is now an object property on evidence links (was an annotation property with string values on markers)
- `RetractionNotice` and `ExpressionOfConcern` use stated-reason links instead of fixed links to `Fabrication`, `Falsification` and `TextPlagiarism`
- `CitationPatternAnomaly` -> `CitationManipulation` is graded (was definitive): citation anomalies are a matter of degree
- Vocabulary resolution follows every parent, nearest first, ties by IRI (`scripts/resolve_vocabulary.py`); ready for classes with several parents
- `tests/test_docs_consistency.py`: `parents()` helper; banned-phrase list updated to match the ontology
- `CITATION.cff`: authors set to "CAVEAT contributors"; Intellicat Inc. listed as contact; abstract added
- `rdfs:label` of `caveat:FailedIndependentReplication` changed to "published failed replication" (was identical to `caveat:FailedReplication`)
- `rdfs:label` of property `caveat:corpusFamily` changed to "member of corpus family" (was identical to class `caveat:CorpusFamily`)

### Fixed
- v0.2.0 attached evidence strengths to markers, so a marker with several links had ambiguous strengths and CQ5 returned a cross product
- `caveat:TorturedPhrases` definition example replaced with one found in the cited source ("counterfeit consciousness")
- `magnetized-water.yaml` header named itself as its parent
- `examples/example-queries.sparql`: CQ5 uses evidence links; CQ2 expected severity corrected to 1.0
- `mappings/README.md` named generator scripts that did not exist
- Removed the orphaned `scripts/build_release.py`; README now describes the artifacts built by `scripts/build_artifacts.py`
- `README.md`: removed nonexistent "cargo cult methodology" category and HermiT validation claim; corrected OpenAlex (schema only, no data yet), BFO/IAO alignment scope, vocabulary coverage and repository layout; usage example now declares its prefixes and topic individual
- `docs/severity-defaults.md`: replaced the "child severity ≥ parent" principle, which 21 classes violate, with the actual rule; listed classes below their parent; replaced nonexistent `CargoCultScience` in the override example; made band boundaries unambiguous; clarified the IEC 60812 relationship
- `docs/index.html`: removed "all classes" definition claim, "traceable causation" and the undeclared `caveat:oa_topic_T12345` IRI; usage example and design principles now match `README.md`
- `docs/bfo-alignment.md`: OpenAlex hierarchy is plain OWL classes, not a SKOS concept scheme; noted other unaligned classes
- `caveat:MagnetizedWater` definition typo ("water water")
- `scripts/validate.py` docstring listed an orphan-class check that does not exist; now lists the checks actually run

## [0.2.0] — 2026-09-14

### Changed
- Project rename to CAVEAT (Controlled Annotation Vocabulary for Epistemic Aberration Types)
- Organization transfer and repository rename to `intellicat-ai/caveat`
- Updated base IRI to `https://w3id.org/intellicat/caveat#` and ontology IRI to `https://w3id.org/intellicat/caveat`
- Updated CURIE prefix to `caveat:`
- Renamed root ontology file to `src/ontology/caveat.ttl`

## [0.1.0] — 2026-04-08

### Added
- Initial ontology structure with BFO/IAO alignment
- Unreliability mode hierarchy (4 top-level categories, ~45 classes)
- Detection marker hierarchy (4 categories, ~18 classes)
- Marker-to-mode evidential links with strength qualifiers
- Scientific domain alignment schema (OpenAlex topics)
- Document annotation schema (properties for downstream consumers)
- Controlled vocabulary schema and initial lexicons for:
  - Pseudoscience (base rejection/sanewashing terms)
  - Vitalist / Energy Medicine (engagement terms)
  - Biofield Energy Healing (engagement terms)
- Example annotations (Trivedi 2016)
- Competency questions with SPARQL sketches
- Scope definition
- Contributing guide with review checklist
