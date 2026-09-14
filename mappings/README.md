# External Vocabulary Mappings

This directory contains SKOS alignments between CAVEAT concepts and external controlled vocabularies. These are informational cross-references, not ontology imports — they do not affect the CAVEAT class hierarchy.

## Files

- `openalex-topics.ttl` — Generated SKOS alignment to OpenAlex topic hierarchy. Created by `scripts/import_openalex_topics.py`.
- `openalex-siblings.ttl` — Sibling relationships between OpenAlex topics. Created by `scripts/import_openalex_siblings.py`.
- `mesh-alignment.ttl` — Manual SKOS alignment to MeSH terms where applicable.
- `retraction-watch-alignment.ttl` — Informal alignment to Retraction Watch retraction reason categories.

## Snapshot Dates

OpenAlex data is actively maintained. Mappings are generated from snapshots:

| File | Snapshot Date | OpenAlex API Version |
|------|--------------|---------------------|
| openalex-topics.ttl | (not yet generated) | — |
| openalex-siblings.ttl | (not yet generated) | — |

## Regeneration

To regenerate OpenAlex mappings:

```bash
python scripts/import_openalex_topics.py
python scripts/import_openalex_siblings.py
```

These scripts require network access to the OpenAlex API.
