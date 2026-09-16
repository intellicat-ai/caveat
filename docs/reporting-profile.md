# Reporting Profile: `caveat-assessment/1`

Pipelines that score papers can explain their scores in CAVEAT terms. The
payload says which unreliability mode a score refers to, which detection
markers support it, who observed them, and how sure everyone is.

The payload is plain JSON. With its JSON-LD context it is also RDF.

- Schema: `https://w3id.org/intellicat/caveat/vocabularies/profiles/assessment-1.schema.json`
- Context: `https://w3id.org/intellicat/caveat/vocabularies/profiles/assessment-1.jsonld`
- Examples: [`vocabularies/profiles/examples/`](https://github.com/intellicat-ai/caveat/tree/main/vocabularies/profiles/examples)
- Checker: `scripts/check_assessment.py`

## Four numbers, kept apart

| Field | Owner | Meaning |
|---|---|---|
| `confidence` | detector | Probability that the marker is really present. `calibrated` says whether it is a calibrated probability or a raw score. |
| `intensity` | detector | Magnitude of a graded marker, 0 to 1. Required when the link strength is graded, such as `CitationPatternAnomaly`. |
| `strength` | CAVEAT | How diagnostic the marker is for the mode. Fixed per evidence link, or derived from `intensity` for graded links. |
| `score` | pipeline | The pipeline's own output for the mode. |

Severity (`caveat:defaultSeverity`) is a fifth number. It belongs to the mode
and lives in the ontology, not in the payload.

Graded strength bands: intensity below 0.25 is weak, from 0.25 moderate, from
0.5 strong, from 0.75 definitive. The bounds are the
`caveat:intensityLowerBound` values on the strength individuals.

## Shape

```json
{
  "profile": "caveat-assessment/1",
  "caveat_version": "0.4.0",
  "document": "https://doi.org/10.5555/caveat.example.1",
  "claimed_topic": "caveatoa:T11636",
  "assessments": [
    {
      "mode": "caveat:Fabrication",
      "score": 1.0,
      "observations": [
        {
          "marker": "caveat:SyntheticSpectra",
          "link": "caveat:evidence_SyntheticSpectra_Fabrication",
          "strength": "caveat:StrongEvidence",
          "confidence": 0.95,
          "calibrated": true,
          "detector": {"pipeline": "example-figure-forensics", "module": "spectrum-synthesis-detector", "version": "1.0"},
          "locator": {"figure": "2", "panel": "b"}
        }
      ]
    }
  ]
}
```

Read it as: the pipeline scores fabrication at 1.0 because a spectra detector observed
synthetic spectra with calibrated confidence 0.95, and CAVEAT rates synthetic
spectra strong evidence for fabrication.

## Rules the checker enforces

- `link` must belong to `marker`.
- A fixed link's mode must equal the assessed `mode` or be a subclass of it.
  Assessing `DataMisconduct` from a `Fabrication` link is valid.
- A stated-reason link (`caveat:evidence_RetractionNotice_stated`,
  `caveat:evidence_ExpressionOfConcern_stated`) needs `stated_mode`: the mode
  the notice itself names. Keep the source wording in `stated_reason`. Fixed
  links must not carry `stated_mode`.
- A graded link needs `intensity`. If `strength` is given it must equal the
  band of the intensity. `caveat:GradedEvidence` is never a valid `strength`.
- `caveat_version` must not be newer than the ontology in use.
- `claimed_topic`, when a taxonomy file is supplied, must be an OpenAlex topic.

```python
from check_assessment import load_graph, check
g = load_graph()                      # once per process
errors = check(payload, g)            # [] means valid
```

## Topics in evidence

`claimed_topic` is the document's OpenAlex topic. Observations that relate the
document to other documents, such as citations to flagged works, use
`related_document` with `topic_relation`, or `topic_relation_counts` when they
summarize many. Relations: `caveat:SameTopic`, `caveat:SameSubfield`,
`caveat:SameField`, `caveat:SameDomain`, `caveat:DifferentDomain`.

## Storing payloads

The payload is self-contained. Store it as is, or nest it under a `caveat`
key inside a larger explanation object; the `profile` field identifies it.
The `@context` key may be omitted in storage and added when the payload is
published as JSON-LD.

## Mapping findings to markers

CAVEAT supplies the IRIs; each pipeline owns the mapping from its findings to
markers.

- A detector may need different markers depending on what it inspected.
  Duplication in blot images is `caveat:ClonedImages`; duplicated spectra
  call for a separate marker.
- A retraction or expression-of-concern feed maps each notice to the
  stated-reason link. The source wording goes to `stated_reason`; the mode it
  maps to goes to `stated_mode`.
