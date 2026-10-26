# Mode Proposals

Changes to the unreliability mode hierarchy (new modes, moves, second parents, rewritten definitions, lexicons, domains, rebuttal links) arrive as proposals. An agent may draft a proposal; a person reviews it; a deterministic script applies it. Nobody hand-edits `src/ontology/modules/unreliability-modes.ttl` to add a mode.

## Lifecycle

1. **Draft.** The proposal is written to `work/<slug>/proposal.yaml` (the `work/` directory is not committed), with `annotation.annotator` set and `annotation.reviewer` empty. Source texts used while drafting go in `work/<slug>/sources/`.
2. **Review.** A person reads the proposal, edits it where needed, and adds their initials as `reviewer`. See [review.md](review.md).
3. **Apply.** On a feature branch with a clean working tree:

   ```bash
   python scripts/authoring/apply_proposal.py work/<slug>/proposal.yaml
   ```

   The script checks the proposal, writes every affected file, runs `scripts/validate.py`, `scripts/check_reviewed.py` and the test suite, and commits. It never pushes. If anything fails, it restores every file it touched and exits with the reason.

## Format

A proposal is YAML validated by `design/proposal.schema.json` (`schema: caveat-proposal/1`).

| Field | Content |
|---|---|
| `slug`, `date` | identifier and date; a slug is used once |
| `intent` | what was asked: `new_mode`, `extend_mode`, `lexicon_only` or `reclassify` |
| `decision` | what is proposed: `new_mode`, `lexicon_only`, `alias`, `reclassify` or `reject` |
| `annotation` | `annotator` and `reviewer` initials |
| `summary` | what the proposal does and why |
| `sources` | the literature relied on, each with a `role` (below) |
| `classes` | class operations, applied in order: `create` or `update` |
| `lexicons` | lexicon files to create, or terms to add to an existing one |
| `domains` | mode-domain links with their measurements (see `mappings/README.md`) |
| `rebuttals` | rebuttal links with their source metadata (see [rebuttals.md](rebuttals.md)) |
| `guidance`, `probes` | the requester's free text and per-paper probe data; never committed |

A class operation names the class and may set `parents` (for an update, the complete new parent set), `label`, `definition`, `definition_source` (an IRI or a literal citation), `comment`, `default_severity`, `severity_rationale`, `lexicon_file`, `related_modes`, and `typically_exhibits` entries with the counts they were harvested from (`k` of `n` sampled works, the query and the date). A create, and any change of parents, records the placement rules that decided it ([placement-rules.md](placement-rules.md)) under `placement`.

## What is committed

The applied proposal is committed as `design/proposals/<slug>.yaml`, minus:

- `guidance` and `probes`;
- sources with role `pointer` (references used only to find primary literature) or `counter_exemplar`;
- exemplars without a `prior_record` (a link to an existing public critique of the paper) and its `archivedAt`.

Dropped items stay in `work/<slug>/` and still count for drafting. CAVEAT names a paper only to ground a class, and is never the first public place a paper is criticized.

## What the script writes

- **Classes.** A new class block goes after the last statement of its first parent's subtree in `unreliability-modes.ttl`, in the house order of predicates. An updated class block is rewritten in place, so a move keeps its position in the file. No other statement is touched, and the script checks that each Turtle file changed by exactly the intended triples. `related_modes` are written in both directions.
- **Lexicons.** A new lexicon file is generated; terms for an existing file are appended. A lexicon the script edits takes the proposal's `annotation`. When a class with a lexicon moves, the lexicon's `inherits_from` follows its first new parent.
- **Domains and rebuttals.** Annotations on the class, rows in `mappings/openalex/mode-domains.csv`, link nodes in `mode-rebuttals.ttl` and rows in `mappings/rebuttals/manifest.jsonl`, all carrying the proposal's annotation.
- **Severity tables.** Both tables in [severity-defaults.md](severity-defaults.md) are brought up to date. A class newly above a parent needs a `severity_rationale`, which becomes its row's rationale.
- **Changelog.** Lines under the Unreleased section for every new mode, move, rewritten definition, relabelling, severity change, association, lexicon, domain and rebuttal.

## Refusals

The script refuses a proposal, and changes nothing, when:

- it does not match the schema, or is not reviewed by a listed reviewer other than its annotator;
- the current branch is `main` or `develop`, or the working tree has uncommitted changes;
- a created class exists, an updated class does not, or a parent is not an unreliability mode;
- it adds a direct child of the root or moves a top-level category (R1);
- a `reject` decision carries changes, or a `lexicon_only` or `alias` decision creates classes or changes parents;
- a `typically_exhibits` entry is below the threshold: at least 5 sampled works and at least 25% of them;
- a class is newly above a parent without a `severity_rationale`;
- any shipped prose (summary, definitions, comments, rationales, placement notes, checks, scopes) shares an 8-word sequence with a source text under `work/<slug>/sources/`;
- the validator, the review check or the test suite fails afterwards.
