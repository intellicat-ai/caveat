# Default Severity in CAVEAT

## Scale Definition

Every unreliability mode below the root `UnreliabilityMode` carries a `caveat:defaultSeverity` value between 0.0 and 1.0. The root has none. Detection markers have none.

The idea is borrowed from the severity dimension of FMEA (Failure Mode and Effects Analysis, IEC 60812). The 0.0 to 1.0 scale and the bands below are CAVEAT's own; they are not an IEC 60812 severity scale.

Bands include their upper bound. A value of exactly 0.4 falls in the second band, not the third.

| Range | Interpretation |
|-------|---------------|
| 0.0 to 0.2 | Minimal impact on paper reliability. Content may still be usable with caveats. |
| above 0.2 to 0.4 | Moderate impact. Specific claims are unreliable but some content may be salvageable. |
| above 0.4 to 0.6 | Substantial impact. Most conclusions are unreliable. |
| above 0.6 to 0.8 | Severe impact. The paper should not be relied upon. |
| above 0.8 to 1.0 | The paper is entirely unreliable or fraudulent. No content is trustworthy. |

## Assignment Principles

1. **Severity reflects the degree of content compromise**, not the moral severity of the misconduct.

2. **Each class is assigned its own value. A parent's value does not bound its children in either direction.** Children sit below their parent in many places. For example, `PredatoryJournalPublication` (default 0.3) is lower than its parent `PublicationProcessMisconduct` (default 0.6) because venue quality is a weaker signal of content quality than, say, compromised peer review. Children also sit above their parent: `CompromisedPeerReview` (default 0.7) is higher than `PublicationProcessMisconduct` (default 0.6).

3. **Severity is assigned to modes, not papers.** A paper's effective severity comes from its primary unreliability mode's default severity, or from a consumer-specific override.

## Current Default Values

The authoritative values are the `caveat:defaultSeverity` annotations (typed `xsd:decimal`) in [`src/ontology/modules/unreliability-modes.ttl`](https://github.com/intellicat-ai/caveat/blob/main/src/ontology/modules/unreliability-modes.ttl). The tables below are checked against that file by `tests/test_docs_consistency.py`.

### Top-level categories

| Category | Default severity |
|---|---|
| `DeliberateMisconduct` | 1.0 |
| `PremiseLevelFailure` | 0.95 |
| `InterpretiveFailure` | 0.6 |
| `ExecutionLevelFailure` | 0.3 |

### Classes below their parent

Every class whose default severity is lower than its parent's. Per-class rationale has not yet been recorded, except for `PredatoryJournalPublication` above.

| Class | Default severity | Parent | Parent default severity |
|---|---|---|---|
| `AuthorshipMisconduct` | 0.6 | `DeliberateMisconduct` | 1.0 |
| `CitationManipulation` | 0.4 | `AuthorshipMisconduct` | 0.6 |
| `GhostAuthorship` | 0.5 | `AuthorshipMisconduct` | 0.6 |
| `GiftAuthorship` | 0.4 | `AuthorshipMisconduct` | 0.6 |
| `SelectiveReporting` | 0.7 | `DataMisconduct` | 1.0 |
| `PublicationProcessMisconduct` | 0.6 | `DeliberateMisconduct` | 1.0 |
| `DuplicatePublication` | 0.4 | `PublicationProcessMisconduct` | 0.6 |
| `PredatoryJournalPublication` | 0.3 | `PublicationProcessMisconduct` | 0.6 |
| `UndisclosedConflictOfInterest` | 0.5 | `PublicationProcessMisconduct` | 0.6 |
| `Denialism` | 0.9 | `PremiseLevelFailure` | 0.95 |
| `SystematicMisinterpretation` | 0.5 | `InterpretiveFailure` | 0.6 |
| `InadequateBlinding` | 0.35 | `DesignFailures` | 0.4 |
| `SelectionBias` | 0.35 | `DesignFailures` | 0.4 |
| `InappropriateGeneralization` | 0.25 | `Overreach` | 0.3 |
| `StatisticalClinicalConflation` | 0.25 | `Overreach` | 0.3 |
| `ReproducibilityFailures` | 0.25 | `ExecutionLevelFailure` | 0.3 |
| `InsufficientMethodDetail` | 0.2 | `ReproducibilityFailures` | 0.25 |
| `NonShareableDataCode` | 0.2 | `ReproducibilityFailures` | 0.25 |
| `InappropriateStatisticalTests` | 0.3 | `StatisticalMalpractice` | 0.35 |
| `MultipleComparisonsUncorrected` | 0.3 | `StatisticalMalpractice` | 0.35 |
| `UnderpoweredStudy` | 0.3 | `StatisticalMalpractice` | 0.35 |

## Consumer Overrides

CAVEAT provides defaults. Downstream projects may override severity for their context:

- A research integrity screening tool might raise `PredatoryJournalPublication` from its default 0.3 to 0.6, because for screening purposes venue quality is a strong signal.
- An LLM benchmark such as TRACES might keep `Pseudoscience` at its default 0.95 but lower `ExecutionLevelFailure` from 0.3 to 0.2, because methodologically flawed but real science is less likely to produce distinctive LLM influence.

The mechanism for overrides is application-specific. CAVEAT does not prescribe how overrides are stored or applied.