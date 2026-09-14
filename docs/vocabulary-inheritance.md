# Vocabulary Inheritance in CAVEAT

## Principle

Each unreliability mode in the CAVEAT hierarchy may have an associated vocabulary file (linked via `caveat:lexiconFile`). A mode's **effective vocabulary** is the union of its own terms and all ancestor terms, collected by traversing the `rdfs:subClassOf` chain from the mode to the root.

## Example

For `caveat:BiofieldEnergyHealing`, the inheritance chain is:

```
BiofieldEnergyHealing
  └── lexicon: engagement/biofield-energy-healing.yaml
  └── parent: VitalistEnergyMedicine
        └── lexicon: engagement/vitalist-energy-medicine.yaml
        └── parent: Pseudoscience
              └── lexicon: rejection/pseudoscience-base.yaml
              └── parent: PremiseLevelFailure (no lexicon)
                    └── parent: UnreliabilityMode (no lexicon)
```

The effective vocabulary for BiofieldEnergyHealing is:

1. All terms from `engagement/biofield-energy-healing.yaml`
2. Plus all terms from `engagement/vitalist-energy-medicine.yaml`
3. Plus all terms from `rejection/pseudoscience-base.yaml`

## Resolution Algorithm

```python
def resolve_vocabulary(mode_uri, graph):
    """Collect all lexicon files from mode to root."""
    lexicon_files = []
    current = mode_uri
    while current:
        lexicon = graph.value(current, CAVEAT.lexiconFile)
        if lexicon:
            lexicon_files.append(str(lexicon))
        parents = list(graph.objects(current, RDFS.subClassOf))
        # Follow only the CAVEAT hierarchy (skip BFO parents)
        current = next(
            (p for p in parents
             if (p, RDFS.subClassOf, CAVEAT.UnreliabilityMode) in graph
             or p == CAVEAT.UnreliabilityMode),
            None
        )
    return lexicon_files
```

The script `scripts/resolve_vocabulary.py` implements this and outputs a flat merged vocabulary for any given mode.

## Term Precedence

When the same term appears at multiple levels (e.g., a term defined at the parent level and redefined at the child level), the more specific (child) definition takes precedence. In practice, this should be rare — child lexicons should add terms, not redefine parent terms.

## Design Rationale

Top-down inheritance ensures that:

1. **Shared terms are defined once.** Rejection terms like "pseudoscience" apply to all pseudoscience subtopics and are defined in `pseudoscience-base.yaml`, not repeated in every subtopic lexicon.

2. **Specificity increases with depth.** The root provides broad terms; leaves provide narrow, corpus-specific terms. This mirrors how the unreliability modes themselves become more specific with depth.

3. **New subtopics get a useful vocabulary immediately.** A newly added pseudoscience subtopic inherits all parent and grandparent terms before any subtopic-specific terms are added.
