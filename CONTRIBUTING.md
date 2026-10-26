# Contributing to CAVEAT

CAVEAT follows the open ontology development workflow described in the
[Scientific Ontology Network's Practical Ontology Development Guide](https://scientific-ontology-network.github.io/).

## Issue-Based Development

All ontology changes start as GitHub issues. Use the appropriate issue template:

- **New unreliability mode**: Propose a new class in the failure mode hierarchy
- **New detection marker**: Propose a new observable marker
- **New lexicon term**: Propose adding a term to a controlled vocabulary
- **Definition problem**: Report an unclear, incorrect, or inconsistent definition
- **New OpenAlex mapping**: Request import of additional OpenAlex topic branches

### Issue Guidelines

1. **Naming**: Name the issue so it reads naturally after "The issue is that ..." Good: "Biofield subcategory missing for crystal healing." Bad: "Add crystal healing."

2. **Keep it focused**: Each issue should address at most five closely related concepts.

3. **Supply definitions**: Propose draft Aristotelian definitions (genus + differentia). "A [new class] is a [parent class] that [differentia]."

4. **Cite sources**: For unreliability modes, cite evidence that the category is real and distinct. For detection markers, cite forensic methods. For lexicon terms, cite the extraction source.

## Working on Issues

1. A maintainer checks whether the proposal is in scope (see SCOPE.md).
2. An assignee is designated to draft the implementation.
3. Discussion proceeds in the issue until consensus is reached.
4. If discussion exceeds 20 comments, it is moved to a development meeting.

## Implementing Changes

1. Create a branch named `{issue-number}-{short-description}` (e.g., `42-add-crystal-healing`).
2. Make changes in the appropriate module file under `src/ontology/modules/`. Changes to the mode hierarchy go through a reviewed proposal applied by `scripts/authoring/apply_proposal.py` (see [docs/proposals.md](docs/proposals.md)), not through hand edits.
3. Run `python scripts/validate.py` to check consistency.
4. Run `python -m pytest tests/` to verify competency questions still pass.
   Install the pre-push hook once with `pip install -r requirements-dev.txt`
   and `pre-commit install --hook-type pre-push`.
5. Update CHANGELOG.md with the issue number and a brief description.
6. Open a Pull Request referencing the issue (`closes #42`).

## Review Checklist

Reviewers should verify:

- [ ] Classes are placed correctly in the hierarchy, by the rules in [docs/placement-rules.md](docs/placement-rules.md)
- [ ] Definitions follow Aristotelian pattern (genus + differentia)
- [ ] Definitions are consistent with parent and sibling class definitions
- [ ] BFO/IAO alignment is correct
- [ ] New classes have all required annotations (label, definition, definitionSource where applicable)
- [ ] Default severity values are assigned and documented
- [ ] Lexicon files (if changed) conform to `vocabularies/_schema.yaml`
- [ ] No unintended changes to other files
- [ ] CHANGELOG.md is updated
- [ ] All automated tests pass

## Vocabulary Contributions

Lexicon contributions follow a slightly different process:

1. Identify the target unreliability mode (must already exist in the ontology).
2. Cite the extraction source (ontology branch, corpus analysis, etc.).
3. Classify each term: engagement, rejection, or sanewashing.
4. Provide rationale for the classification.
5. Submit via the "New lexicon term" issue template.

## Review of Agent-Authored Records

The full rules are in [docs/review.md](docs/review.md). In short:

Records written with an agent's help (lexicon files, and in later releases
proposal records, rebuttal manifest rows and mode-domain rows) carry an
`annotation` block with `annotator` and `reviewer` initials, as in TRACES.
A record is complete only when a person has reviewed it and added their
initials as `reviewer`. The reviewer must be listed in `.reviewers` and
must differ from the annotator. An agent never fills in the `reviewer`
field.

`scripts/check_reviewed.py` enforces this as a `pre-push` hook and again
in CI, because local hooks can be skipped. The check catches a forgotten
review. It cannot tell initials typed by a person from initials typed by
an agent; that part rests on the rule above.

## Code of Conduct

All contributors are expected to engage constructively and in good faith. Ontology development is consensus creation — disagreements about classification are expected and welcome when supported by evidence.

## Releasing

1. On `develop`, the top `CHANGELOG.md` section is `## [X.Y.Z] - Unreleased`, and `owl:versionInfo` in `src/ontology/caveat.ttl` and `version` in `docs/_config.yml` are `X.Y.Z`. `tests/test_versions.py` enforces this.
2. Run `python scripts/set_release.py X.Y.Z YYYY-MM-DD`. It dates the changelog section and updates `CITATION.cff` and `dcterms:modified`.
3. Run the test suite and `cffconvert --validate`, merge `develop` into `main`, and tag `vX.Y.Z`.
4. After the documentation site deploys, check that the published IRIs resolve.
