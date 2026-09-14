# Default Severity in CAVEAT

## Scale Definition

CAVEAT assigns a `defaultSeverity` value (0.0 to 1.0) to each unreliability mode, following FMEA (Failure Mode and Effects Analysis) conventions from IEC 60812.

| Range | Interpretation |
|-------|---------------|
| 0.0–0.2 | Minimal impact on paper reliability. Content may still be usable with caveats. |
| 0.2–0.4 | Moderate impact. Specific claims are unreliable but some content may be salvageable. |
| 0.4–0.6 | Substantial impact. Most conclusions are unreliable. |
| 0.6–0.8 | Severe impact. The paper should not be relied upon. |
| 0.8–1.0 | Paper is entirely unreliable or fraudulent. No content is trustworthy. |

## Assignment Principles

1. **Severity reflects the degree of content compromise**, not the moral severity of the misconduct.

2. **Child severity ≥ parent severity by default**, but children may override in either direction with documented rationale. For example, `PredatoryJournalPublication` (0.3) is lower than its parent `PublicationProcessMisconduct` (0.6) because venue quality is a weaker signal of content quality than, say, compromised peer review.

3. **Severity is assigned to modes, not papers.** A paper's effective severity comes from its primary unreliability mode's default severity (or from consumer-specific overrides).

## Consumer Overrides

CAVEAT provides defaults. Downstream projects may override severity for their context:

- A research integrity screening tool might weight `PredatoryJournalPublication` higher (0.6) because for screening purposes, venue quality is a strong signal.
- An LLM benchmark like TRACES might weight `Pseudoscience` at 0.95 (the default) but weight `CargoCultScience` lower (0.2) because methodologically flawed but real science is less likely to produce distinctive LLM influence.

The mechanism for overrides is application-specific. CAVEAT does not prescribe how overrides are stored or applied.

## Current Default Values

See `src/ontology/modules/unreliability-modes.ttl` for the full set of default severity assignments. The values are attached as `caveat:defaultSeverity` annotation properties on each class.
