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

A mode may have more than one parent (see [placement-rules.md](placement-rules.md), R3 and R4). Resolution therefore walks every CAVEAT parent, breadth-first:

1. Collect the mode and all its CAVEAT ancestors, each with its distance from the mode (the shortest path when an ancestor is reachable along several).
2. Order them nearest first; ancestors at the same distance are ordered by IRI.
3. Take each ancestor's `caveat:lexiconFile` in that order, listing each file once.

```python
def get_ancestor_chain(g, mode_uri):
    """Breadth-first over all CAVEAT parents. Nearest first; ties by IRI."""
    dist = {mode_uri: 0}
    frontier = [mode_uri]
    while frontier:
        nxt = set()
        for node in frontier:
            for p in g.objects(node, RDFS.subClassOf):
                if str(p).startswith(str(CAVEAT)) and p not in dist:
                    dist[p] = dist[node] + 1
                    nxt.add(p)
        frontier = sorted(nxt, key=str)
    return sorted(dist, key=lambda u: (dist[u], str(u)))
```

The script `scripts/resolve_vocabulary.py` implements this and outputs a flat merged vocabulary for any given mode. The release's `modes.csv` reports, for every mode, the number of terms its resolved vocabulary holds (`lexicon_terms_resolved`).

## Term Precedence

When the same term appears at multiple levels (e.g., a term defined at the parent level and redefined at the child level), the more specific (child) definition takes precedence: the file nearest the mode in the order above wins. In practice, this should be rare — child lexicons should add terms, not redefine parent terms.

## Design Rationale

Top-down inheritance ensures that:

1. **Shared terms are defined once.** Rejection terms like "pseudoscience" apply to all pseudoscience subtopics and are defined in `pseudoscience-base.yaml`, not repeated in every subtopic lexicon.

2. **Specificity increases with depth.** The root provides broad terms; leaves provide narrow, corpus-specific terms. This mirrors how the unreliability modes themselves become more specific with depth.

3. **New subtopics get a useful vocabulary immediately.** A newly added pseudoscience subtopic inherits all parent and grandparent terms before any subtopic-specific terms are added.
