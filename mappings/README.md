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

## Mode domains (`openalex/mode-domains.csv`)

`caveat:dedicatedDomain` and `caveat:hostDomain` (sub-properties of the abstract `caveat:candidateDomain`) link an unreliability mode to OpenAlex topics or subfields of the pinned taxonomy. The ontology carries the IRIs only; this file carries the measurements behind each link, one row per link, and the tests require the two to match.

- **Dedicated** is a semantic judgment, not a statistic: the topic's label and characteristic keywords name the mode's constructs, and the mode is the lowest class whose subtree covers them. A mode has at most one dedicated domain, and a topic is dedicated to at most one mode. A paper in a dedicated domain is presumed to belong to that mode or a descendant.
- **Host** means the mode's papers concentrate in the topic. The mode's share of a host topic is measured, not asserted, and membership alone is never evidence of the mode.

| Column | Content |
|---|---|
| `mode`, `topic`, `kind` | the link: mode CURIE, `caveatoa:` topic or subfield, `dedicated` or `host` |
| `covered_keywords`, `uncovered_keywords` | the topic's OpenAlex keywords the mode does and does not cover (`\|`-separated) |
| `seed_n`, `share_of_seed` | works matching the mode's high-precision terms, and the share of them in this topic |
| `probe_random_n`, `probe_random_hits`, `probe_random_ci` | a uniform random sample of the topic's works labelled against the mode's definition, with a Wilson 95% interval for the share |
| `probe_topcited_n`, `probe_topcited_hits`, `probe_topcited_ci` | the same for the topic's most-cited works |
| `query`, `taxonomy_version`, `date` | how the measurement was made, against which taxonomy snapshot, and when |
| `annotator`, `reviewer` | see [docs/review.md](../docs/review.md) |

Consumers may use a probe interval as a prior. It never substitutes for a lexicon or marker hit. Only these aggregates are published; the per-paper probe labels are not. Neither this file nor the ontology characterizes a topic in prose: the numbers are the record.

## Rebuttal sources (`rebuttals/`)

`manifest.jsonl` lists the sources cited by `caveat:RebuttalLink` nodes, validated by `manifest.schema.json`. See [docs/rebuttals.md](../docs/rebuttals.md).

## Planned

MeSH and Retraction Watch alignments are planned; see [`ROADMAP.md`](../ROADMAP.md).
