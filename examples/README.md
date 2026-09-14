# CAVEAT Usage Examples

This directory contains ABox (assertional) examples showing how to annotate
documents using the CAVEAT ontology. These are illustrative — they demonstrate
correct usage patterns, not a comprehensive corpus.

## Files

- `trivedi-2016.ttl` — Annotating a biofield energy healing paper from a predatory journal, with corpus family assignment.
- `example-queries.sparql` — SPARQL queries demonstrating competency questions against the example data.

## How to Use

1. Import the CAVEAT ontology: `owl:imports <https://w3id.org/intellicat/caveat>`
2. Create individuals of type `caveat:AnnotatedDocument`
3. Assign `caveat:primaryUnreliabilityMode` (exactly one)
4. Optionally assign `caveat:secondaryUnreliabilityMode` (zero or more)
5. Optionally record `caveat:detectionMarkerObserved` (zero or more)
6. Assign `caveat:claimedDomain` to an OpenAlex topic (if domain classification is relevant)
7. Assign `caveat:corpusFamily` if the document belongs to a known group

## Note on Severity

CAVEAT provides `caveat:defaultSeverity` on each unreliability mode class.
Downstream projects may override these values for their specific context.
To query the default severity for a document's primary mode:

```sparql
SELECT ?doc ?mode ?severity WHERE {
  ?doc caveat:primaryUnreliabilityMode ?mode .
  ?mode caveat:defaultSeverity ?severity .
}
```
