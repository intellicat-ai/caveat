# Placement Rules

These rules decide where an unreliability mode goes in the hierarchy, whether it gets a second parent, whether it gets children, and what it is called. Every new or moved mode records the rule that decided its placement. If the rules do not decide a case, or two of them conflict, the case goes to review instead of being settled by improvisation.

## R1. The top level is fixed

There are four categories: `DeliberateMisconduct`, `PremiseLevelFailure`, `InterpretiveFailure` and `ExecutionLevelFailure`. `tests/test_ontology.py` pins them. New modes go below them.

## R2. Pseudoscience, unphysical claims, denialism, pathological science

Four differentiae separate the premise-level classes from each other and from pathological science:

- **Pseudoscience** (`Pseudoscience`): the work advances constructs of its own (energies, doctrines, entities) that have been investigated and found baseless.
- **Unphysical mechanism**: the central claim is excluded by first principles (conservation laws, quantum ground states, known relaxation timescales), whether or not anyone ran the experiment.
- **Denialism** (`Denialism`): the claim is defined by its opposition to an established consensus and is pursued with the denialist toolkit: conspiracy, fake experts, selective citation, impossible expectations, misrepresentation.
- **Pathological science** (`PathologicalScience`, interpretive, not premise-level): an effect at the limit of detection, championed by one school and defended by ad hoc excuses (Langmuir).

The test is construct versus consensus, not "asserts a false positive" versus "denies an established one". Most denialist claims do both: they assert a harm that does not exist and deny a finding that does. Classes may migrate between these as evidence accumulates; every migration is recorded in `CHANGELOG.md`.

## R3. Doctrine axis and mechanism axis

Inside `Pseudoscience`, an intermediate class is either a doctrine (who believes it, and on what authority, as with `Parapsychology`) or a mechanism family (which physical claim is false, as with `VitalistEnergyMedicine`). A leaf may have one parent on each axis.

## R4. Polyhierarchy only for stable intersections

A second `rdfs:subClassOf` requires that every instance of the class is an instance of both parents, and that the intersection has a literature of its own. Two modes that merely co-occur in a paper are handled by labelling the paper with both. A looser association between modes uses `caveat:relatedMode`, or `caveat:typicallyExhibits` when papers of one mode commonly show the other.

## R5. Publication footprint

A topic gets a mode only if it has a published-science record: by default at least 25 works in OpenAlex matching its high-precision terms, from at least 3 independent author groups. No footprint, no mode, however notorious the topic. A small but real literature qualifies. A controversy confined to a single episode is a matter for paper-level annotation, not a mode. The defaults will be revisited once a first batch of candidate topics has been measured.

## R6. Severity is a property of the mode

`caveat:defaultSeverity` measures how far the mode compromises a paper's content, not how valuable the paper is. A correct but pointless paper has a low severity. Severity is never lowered because a lexicon or a consumer's rule over-matches: precision belongs in the definition's exclusions, the lexicon levels and the consumer's rules. A child may have a higher default severity than its parent; every such case is listed with its rationale in [severity-defaults.md](severity-defaults.md).

## R7. Heritage traditions are doctrines codified before 1900

Within alternative medicine, a heritage tradition is a doctrine codified before 1900; a modern one originated later. The cutoff is genealogical, not epistemic, and carries no severity difference. It is fixed: a sliding age would move traditions between the two classes over time. A derivative practice inherits the tradition whose constructs it invokes; a derivative built on new constructs is modern. The heritage and modern classes are not declared disjoint, since a leaf can belong to a tradition and to a modern mechanism family at once (R3).

## R8. Exclusions are in the definition

The definition of every alternative-medicine mode excludes ethnopharmacology, phytochemistry, fingerprinting, pharmacokinetics and toxicity studies of the tradition's materials. A paper belongs to the mode only when it explains or predicts an effect through the tradition's constructs, or tests a tradition-specific claim as if the construct were real.

## R9. Moves are free, renames are expensive

Moving a class keeps its IRI. Renaming it breaks finding codes, consumers and the corpora that cite it, such as TRACES. Existing IRIs are not renamed; labels may change. Where an existing corpus already cites a local name for a class that does not exist yet, the new class takes that name.

## R10. Split on evidence, not on appetite

A class gets children only when the candidates differ in default severity, or when term extraction yields separable term sets: each child's high-precision terms rarely match the sibling's exemplars. Otherwise the variants stay as clauses in one definition.

## R11. Finding codes read as failures

A mode's finding code is its local name in snake_case (`ColdFusionLENR` becomes `cold_fusion_lenr`), and users see it. It must not read as an accusation against a legitimate method. Where the method itself is legitimate, the name carries the failure word: formulaic, unprovenanced, misapplication.

## Contrasts worth keeping

**Execution-level ritual versus pathological science.** A study can reproduce the outward form of an investigation (apparatus, controls, assay panels, statistics) without any feature that would let the result come out against the hypothesis. That is an execution-level failure defined by form, and the intent may be honest. Pathological science is different: a real attempt to measure an effect at the detection limit, defended ad hoc when it fails to replicate. The two can share a host topic. In a single literature, routine parameter-sweep simulations can be ritual while earlier experimental claims of an anomalous effect are pathological. Each paper is placed by its own differentia, not by its topic.

**Parentage versus association.** `rdfs:subClassOf` asserts something about every instance. `caveat:typicallyExhibits` asserts only that sampled papers of one mode commonly show another, and its values are harvested from papers with the counts recorded in the proposal record. A paper's category stays decidable from its primary mode because connections across categories go through these associations and through detection markers, not through parentage.
