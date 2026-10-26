# Review of Agent-Authored Records

CAVEAT accepts records drafted with the help of an agent: term lists, proposed modes, domain mappings, rebuttal sources. An agent can propose any of these. None of them is complete until a person has reviewed it. The model follows the TRACES corpus: each record carries `annotator` and `reviewer` initials.

## Records that carry a review

| Record | Where | Field |
|---|---|---|
| Lexicon files | `vocabularies/**/*.yaml` | top-level `annotation: {annotator, reviewer}` |
| Committed proposal records | `design/proposals/*.yaml` | top-level `annotation: {annotator, reviewer}` |
| Rebuttal sources | `mappings/rebuttals/manifest.jsonl` | `annotator` and `reviewer` on every row |
| Mode domains | `mappings/openalex/mode-domains.csv` | `annotator` and `reviewer` columns on every row |

An agent-written record uses `annotator: agent`. Proposal records also name their exemplar papers; every exemplar needs a `prior_record`, a link to an existing public critique of the paper. CAVEAT names a paper only to ground a class, and never as the first public place that paper is criticized.

## Rules

- `reviewer` is not empty, and the initials are listed in `.reviewers`.
- `reviewer` differs from `annotator`. While CAVEAT has a single maintainer, a person listed in `.reviewers` may review their own records. Agent-authored records always need a listed reviewer who is not the annotator. This exception will be removed when a second reviewer joins.
- An agent never fills in the `reviewer` field. Reviewing means reading the record and editing it where needed, then adding your initials.

## Enforcement

`scripts/check_reviewed.py` checks every record above. It runs twice:

1. as a `pre-push` hook, configured in `.pre-commit-config.yaml`. Install it once:

   ```bash
   pip install -r requirements-dev.txt
   pre-commit install --hook-type pre-push
   ```

2. in CI, because local hooks are skipped by `git push --no-verify`.

The check catches a forgotten review. It cannot tell initials typed by a person from initials typed by an agent; that part rests on the rule that an agent never writes them.
