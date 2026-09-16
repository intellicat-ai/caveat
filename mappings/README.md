# External Vocabulary Mappings

## OpenAlex (`openalex/`)

| File | Content |
|---|---|
| `openalex-taxonomy.jsonl` | Normalized OpenAlex domains, fields, subfields and topics. Source of truth for the Turtle files. |
| `manifest.json` | Fetch provenance, counts, sibling statistics, and counts of every value the fetcher normalized. |
| `openalex.ttl` | SKOS concepts under `caveatoa:` (`https://w3id.org/intellicat/caveat/modules/openalex#`). Published as `modules/openalex.ttl`. |
| `openalex-siblings.ttl` | Sibling relations at all four levels, exactly as listed by OpenAlex. Published as `modules/openalex-siblings.ttl`. |

Regenerate. The API key lives in `config/openalex.toml`, which is git-ignored; `config/openalex.example.toml` is the template.

```bash
cp config/openalex.example.toml config/openalex.toml   # then add your key
python scripts/fetch_openalex_taxonomy.py --source api
python scripts/build_openalex_mapping.py
python scripts/build_openalex_mapping.py --check
```

## Planned

MeSH and Retraction Watch alignments are planned; see [`ROADMAP.md`](../ROADMAP.md).
