# Rebuttal Links

A rebuttal link records that a source contains evidence that the claims characteristic of an unreliability mode are unreliable. Links live in `src/ontology/modules/mode-rebuttals.ttl`; the sources they cite, with their metadata and review, live in `mappings/rebuttals/manifest.jsonl`.

## The link

Each link is a named `caveat:RebuttalLink` node, as marker-to-mode evidence links are:

| Property | Value |
|---|---|
| `caveat:rebutsMode` | the unreliability mode |
| `caveat:rebuttalSource` | the source: its DOI IRI (`https://doi.org/...`) where one exists, otherwise its canonical URL |
| `caveat:rebuttalKind` | what the source contains (below) |
| `caveat:rebuttalScope` | optional: the claims within the mode that the source addresses, when narrower than the whole mode |
| `caveat:archivedAt` | an archived copy; required when the source has no DOI |

`caveat:rebuttedBy` is a mode-to-source shortcut, always equal to the projection of the links. A link node's local name is `rebuttal_` followed by the mode's local name and the source's manifest id. Rebuttal links, like `caveat:relatedMode`, are not inherited by subclasses.

## What a source contains, not where it appeared

Peer review is not a criterion. Sources are judged by the evidence they contain. Independent forensic work posted on a blog, on PubPeer or as a preprint often precedes any action by a publisher by years, and an editorial is no stronger for appearing in a journal. Two separate fields replace any ranking of venues: the kind of evidence, and the venue type, which is recorded but never ranked.

Primary evidence (`caveat:PrimaryRebuttalKind`) is preferred over secondary (`caveat:SecondaryRebuttalKind`) whatever the venue:

| Kind | Tier | The source contains |
|---|---|---|
| `caveat:Replication` | primary | an independent attempt to reproduce the claimed effect that did not reproduce it |
| `caveat:ForensicAnalysis` | primary | a documented reanalysis of the work's own data, images, text or code |
| `caveat:Reanalysis` | primary | a pooled or meta-analytic reanalysis of the studies bearing on the claim |
| `caveat:FirstPrinciplesAnalysis` | primary | an analysis showing the claim is excluded by established principles |
| `caveat:InstitutionalFinding` | primary | a retraction, expression of concern or misconduct finding |
| `caveat:Investigation` | secondary | a journalistic or independent investigation assembling others' primary evidence |
| `caveat:NarrativeReview` | secondary | a review without a systematic or pooled analysis |
| `caveat:PositionStatement` | secondary | the stated position of a professional or scientific body |
| `caveat:Explainer` | secondary | an account for a general audience |

A PubPeer thread documenting duplicated images is primary evidence; an editorial asserting the opposite is secondary.

## The manifest

`mappings/rebuttals/manifest.jsonl` holds one JSON object per source, validated by `mappings/rebuttals/manifest.schema.json`:

| Field | Content |
|---|---|
| `id` | stable snake_case key, used in link node names |
| `source` | the `caveat:rebuttalSource` IRI |
| `doi` | the DOI, where one exists; then `is_retracted` records its retraction status when retrieved |
| `archivedAt` | archived copy; required when there is no DOI |
| `openalex_id` | the OpenAlex work id, where applicable |
| `title`, `year` | as published |
| `venueType` | `journal`, `preprint`, `blog`, `pubpeer`, `database`, `institutional` or `news` |
| `retrieved` | date the source was resolved |
| `annotator`, `reviewer` | see [review.md](review.md) |

Every identifier in the manifest comes from a resolver or API lookup, never from memory; a source that cannot be resolved is not added. Only links and metadata ship: no quoted text, abstracts or full-text passages from the sources.
