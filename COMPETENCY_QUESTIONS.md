# CAVEAT Competency Questions

These questions define what CAVEAT should be able to answer. They guide ontology development and serve as acceptance criteria. Each question is paired with a SPARQL query sketch that should return correct results when run against a conformant CAVEAT knowledge base.

## Core Classification

**CQ1**: What unreliability modes does document X have?

```sparql
SELECT ?mode ?role WHERE {
  ex:doc_X caveat:primaryUnreliabilityMode ?mode .
  BIND("primary" AS ?role)
} UNION {
  ex:doc_X caveat:secondaryUnreliabilityMode ?mode .
  BIND("secondary" AS ?role)
}
```

**CQ2**: What is the default severity of document X's primary failure mode?

```sparql
SELECT ?severity WHERE {
  ex:doc_X caveat:primaryUnreliabilityMode ?mode .
  ?mode caveat:defaultSeverity ?severity .
}
```

**CQ3**: What top-level category does unreliability mode Y fall under?

```sparql
SELECT ?category WHERE {
  ?mode rdfs:subClassOf+ ?category .
  ?category rdfs:subClassOf caveat:UnreliabilityMode .
  FILTER(?mode = caveat:BiofieldEnergyHealing)
  BIND(?category AS ?category)
}
```

## Detection Markers

**CQ4**: What detection markers have been observed for document X?

```sparql
SELECT ?marker WHERE {
  ex:doc_X caveat:detectionMarkerObserved ?marker .
}
```

**CQ5**: Which detection markers are evidence for unreliability mode Y?

```sparql
SELECT ?marker ?strength WHERE {
  ?link a caveat:EvidenceLink ;
        caveat:linkMarker ?marker ;
        caveat:linkMode ?mode ;
        caveat:evidenceStrength ?s .
  ?s rdfs:label ?strength .
  FILTER(?mode = caveat:PapermillOperation)
}
```

**CQ6**: Which unreliability modes could be indicated by detection marker M?

```sparql
SELECT ?mode WHERE {
  caveat:TorturedPhrases caveat:evidenceFor ?mode .
}
```

## Scientific Domain

**CQ7**: What is the claimed scientific domain of document X?

```sparql
SELECT ?topic ?subfield ?field ?domain WHERE {
  ex:doc_X caveat:claimedDomain ?topic .
  ?topic caveat:parentSubfield ?subfield .
  ?subfield caveat:parentField ?field .
  ?field caveat:parentDomain ?domain .
}
```

**CQ8**: What are the sibling topics of topic T?

```sparql
SELECT ?sibling WHERE {
  caveat:oa_topic_T12345 caveat:siblingTopic ?sibling .
}
```

## Vocabulary Inheritance

**CQ9**: What is the full inherited vocabulary for unreliability mode Y?

This requires traversing the class hierarchy and collecting lexicon file references:

```sparql
SELECT ?mode ?lexiconFile WHERE {
  caveat:BiofieldEnergyHealing rdfs:subClassOf* ?mode .
  ?mode caveat:lexiconFile ?lexiconFile .
}
```

The downstream consumer then loads and merges all referenced lexicon files.

**CQ10**: What is the parent chain for unreliability mode Y?

```sparql
SELECT ?ancestor WHERE {
  caveat:BiofieldEnergyHealing rdfs:subClassOf+ ?ancestor .
  ?ancestor rdfs:subClassOf* caveat:UnreliabilityMode .
}
ORDER BY DESC(?depth)
```

## Cross-Dimensional Queries

**CQ11**: Which documents in domain D have unreliability mode Y?

```sparql
SELECT ?doc WHERE {
  ?doc caveat:claimedDomain caveat:oa_topic_T12345 .
  ?doc caveat:primaryUnreliabilityMode caveat:Pseudoscience .
}
```

**CQ12**: Which corpus family does document X belong to?

```sparql
SELECT ?family WHERE {
  ex:doc_X caveat:corpusFamily ?family .
}
```
