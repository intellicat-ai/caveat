# CAVEAT Controlled Vocabularies

This directory contains domain-specific terminology intrinsic to each unreliability mode in the CAVEAT ontology. Vocabularies are stored as YAML files and are linked to ontology classes via the `caveat:lexiconFile` annotation property.

## Structure

- `rejection/` — Terms indicating rejection of or distancing from the pseudoscientific premise. These are typically shared across related subtopics. Each term is classified by function: `categorical_rejection`, `evidence_absence`, `mechanism_absence`, `sanewashing_mild`, `sanewashing`, or `sanewashing_strong`.

- `engagement/` — Terms characteristic of specific pseudoscience or unreliability domains. These are the distinctive vocabulary that identifies the domain. Present in the engagement directory because they indicate a response is operating within the pseudoscientific frame.

## Vocabulary Inheritance

Vocabularies inherit top-down through the unreliability mode hierarchy. A mode's effective vocabulary is the union of its own terms and all ancestor terms. For example:

```
BiofieldEnergyHealing effective vocabulary =
    biofield-energy-healing.yaml (own terms)
  + vitalist-energy-medicine.yaml (parent)
  + pseudoscience-base.yaml (grandparent — rejection terms)
```

The `scripts/resolve_vocabulary.py` script computes the full inherited vocabulary for any mode.

## File Format

All lexicon files must conform to `_schema.yaml`. See that file for field definitions and validation rules.

## Adding Terms

To propose new terms, use the "New lexicon term" issue template. Each term must include:

1. The term itself
2. The target unreliability mode
3. Classification (engagement, rejection, or sanewashing)
4. Rationale for the classification
5. Extraction source (corpus analysis, ontology branch, expert judgment)
