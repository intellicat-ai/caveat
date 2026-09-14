# External Ontology Imports

This directory contains minimal excerpts from external ontologies that CAVEAT
directly depends on (i.e., subclasses from).

## bfo-excerpt.ttl

- **Source**: Basic Formal Ontology (BFO) 2020
- **Full ontology**: https://basic-formal-ontology.org/
- **Version imported from**: BFO 2020 (ISO/IEC 21838-2)
- **Classes imported**: BFO_0000001 (entity), BFO_0000002 (continuant), BFO_0000020 (specifically dependent continuant), BFO_0000019 (quality)
- **Rationale**: CAVEAT unreliability modes and detection markers are modeled as qualities (BFO_0000019) inhering in information content entities.
- **Last updated**: 2026-04-08

## iao-excerpt.ttl

- **Source**: Information Artifact Ontology (IAO)
- **Full ontology**: https://github.com/information-artifact-ontology/IAO
- **Classes imported**: IAO_0000030 (information content entity), BFO_0000031 (generically dependent continuant)
- **Rationale**: Scientific publications annotated by CAVEAT are information content entities (IAO_0000030).
- **Last updated**: 2026-04-08

## Why Excerpts, Not Full Imports

Full imports of BFO and IAO would bring in hundreds of classes irrelevant to CAVEAT, increasing load time and complexity for consumers. We import only the classes we directly subclass from. Downstream projects that need the full BFO/IAO can import them alongside CAVEAT without conflict.
