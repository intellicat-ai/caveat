# BFO and IAO Alignment

## Why BFO?

CAVEAT aligns to the Basic Formal Ontology (BFO) and the Information Artifact Ontology (IAO) for interoperability with the large ecosystem of scientific ontologies that use BFO as their upper ontology, including the OBO Foundry ontologies, the Common Core Ontologies (CCO), and the Open Energy Ontology (OEO).

## Alignment Decisions

### Unreliability Modes → BFO Quality

`caveat:UnreliabilityMode rdfs:subClassOf bfo:BFO_0000019` (quality)

An unreliability mode is a quality that inheres in an information content entity (a scientific publication). It is a specifically dependent continuant: it exists only because the publication exists, and it characterizes a property of that publication.

Alternative considered: modeling modes as `bfo:BFO_0000015` (process). This was rejected because an unreliability mode is not something that happens — it is a static property of the published artifact.

### Detection Markers → BFO Quality

`caveat:DetectionMarker rdfs:subClassOf bfo:BFO_0000019` (quality)

A detection marker is also a quality of the publication — an observable feature that inheres in the document. The same reasoning as for unreliability modes applies.

### Annotated Documents → IAO Information Content Entity

`caveat:AnnotatedDocument rdfs:subClassOf iao:IAO_0000030` (information content entity)

A scientific publication is an information content entity: it is generically dependent on some artifact (a PDF, a web page, a printed copy) and stands in a relation of aboutness to some research.

### OpenAlex Hierarchy: Not BFO-Aligned

The OpenAlex hierarchy is modeled as four OWL classes: `OpenAlexDomain`, `OpenAlexField`, `OpenAlexSubfield` and `OpenAlexTopic`. They are linked by `caveat:parentDomain`, `caveat:parentField` and `caveat:parentSubfield`, and entities at each level are related by the sibling properties (`caveat:siblingDomain`, `caveat:siblingField`, `caveat:siblingSubfield`, `caveat:siblingTopic`), which carry the sibling lists OpenAlex publishes. Each of the four classes is a subclass of `skos:Concept`, and the parent properties are sub-properties of `skos:broader`; none has a BFO superclass. They describe an external classification that CAVEAT refers to, not entities CAVEAT defines.

SKOS is not used anywhere in the ontology. `mappings/README.md` describes planned SKOS alignment files; none have been generated.

### Other Unaligned Classes

`CorpusFamily` and `RetractionRecord` are also not aligned to BFO or IAO.

## Minimal Import Strategy

We import only the specific BFO and IAO classes we directly subclass from:

- `bfo:BFO_0000001` (entity)
- `bfo:BFO_0000002` (continuant)
- `bfo:BFO_0000020` (specifically dependent continuant)
- `bfo:BFO_0000019` (quality)
- `bfo:BFO_0000031` (generically dependent continuant)
- `iao:IAO_0000030` (information content entity)

This keeps CAVEAT lightweight while maintaining correct alignment. Projects that need the full BFO or IAO can import them alongside CAVEAT without conflict, because our excerpt uses the same URIs.

### Evidence and Assessment Classes

`EvidenceLink`, `MarkerObservation` and `ModeAssessment` are information content entities (`IAO_0000030`): each records a claim about markers, modes or documents. `Detector` is a subclass of `prov:Agent`, since a detector may be software, a curated database or a person. `EvidenceStrength` and `TopicRelation` are value partitions and have no upper-ontology superclass.
