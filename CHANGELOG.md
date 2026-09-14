# CAVEAT Changelog

All notable changes to this ontology will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/).

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
