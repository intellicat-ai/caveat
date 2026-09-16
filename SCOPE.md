# CAVEAT Scope Definition

## In Scope

This ontology defines terms for classifying unreliable scientific literature and the markers used to detect it. Specifically, CAVEAT covers:

1. **Unreliability modes** — a hierarchical classification of how and why a scientific publication is unreliable, organized by cause (deliberate, premise-level, interpretive, execution-level) and graduated by default severity.

2. **Detection markers** — observable features of publications that serve as evidence for one or more unreliability modes. These are linked to modes via many-to-many evidential relationships with strength qualifiers.

3. **Controlled vocabularies** — domain-specific terminology intrinsic to each unreliability mode (particularly pseudoscience subtopics), classified by function (engagement, rejection, sanewashing). These vocabularies inherit top-down through the mode hierarchy.

4. **Scientific domain classification** — lightweight alignment to external controlled vocabularies (primarily OpenAlex topics) for classifying what field a paper claims to contribute to, including the sibling lists OpenAlex publishes for each level.

5. **Document annotation schema** — OWL properties for annotating individual documents or corpus families with unreliability modes, detection markers, and domain classifications. CAVEAT defines the *schema* for such annotations.

6. **Assessment reporting** — a schema and JSON profile for reporting which detection markers a detector observed in a document, with what confidence, and which unreliability mode a pipeline assessed from them.

## Out of Scope

CAVEAT does **not** cover:

- The content of legitimate science beyond domain classification
- General bibliometric metadata (covered by Dublin Core, SPAR ontologies)
- Detailed research methodology description (covered by OBI, IAO)
- Specific forensic detection algorithms or software tools
- LLM benchmark methodology, scoring formulas, or probe construction (these are application-specific concerns for downstream consumers such as TRACES)
- Judgments about specific individual papers (CAVEAT provides the vocabulary; individual assessments are ABox data maintained by consumers)
- Retraction decisions or editorial policy

## Boundary Cases

- **Severity values**: CAVEAT provides default severity annotations as guidance. Consumers may override these for their specific context. The defaults are part of the ontology; overrides are not.
- **Scores in reports**: The reporting profile carries a pipeline's score, confidence and intensity values. How those numbers are computed is out of scope.
- **Lexicon scoring weights**: CAVEAT classifies terms by function (engagement, rejection, sanewashing). Numerical weights for scoring formulas are application-specific and out of scope.
- **OpenAlex topic data**: CAVEAT imports and aligns to OpenAlex topics but does not replicate the full OpenAlex dataset. The full four-level taxonomy (domains, fields, subfields, topics) is imported as SKOS concepts in a separate artifact; works and counts are not.
