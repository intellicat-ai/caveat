# Term Frequency Bands in CAVEAT Vocabularies

## Purpose

The `general_frequency` field on vocabulary terms captures how common or unusual a term is in general-purpose text. This is distinct from the `level` field, which captures specificity within the pseudoscience domain hierarchy. Both are useful; they answer different questions.

## The Two Dimensions

### `level` — Where in the pseudoscience taxonomy is this term diagnostic?

This field is **internal to the CAVEAT hierarchy**. It answers: "Does this term identify a broad pseudoscience family, a specific subtopic, or a single corpus?"

| Value | Question it answers | Example |
|-------|-------------------|---------|
| `domain_defining` | Is this the core vocabulary of this pseudoscience category? | "biofield energy" defines the biofield healing domain |
| `domain_characteristic` | Is this term typical of this category but shared with siblings or parent? | "sham healer" is used across biofield study designs |
| `corpus_specific` | Is this term unique to one corpus family? | "trivedi effect" only appears in the Trivedi network |

### `general_frequency` — How surprising is this phrase in ordinary text?

This field is **external to CAVEAT**. It answers: "If I encountered this phrase in a random document, how unusual would it be?" It says nothing about pseudoscience — it's a property of the phrase in general language.

| Value | Question it answers | Example |
|-------|-------------------|---------|
| `common` | Would a newspaper reader encounter this? | "clinical trial", "immune system" |
| `specialized` | Would a science graduate encounter this? | "immunomodulatory", "splenocyte" |
| `rare` | Would you need to be in a niche field to encounter this? | "energy healing", "therapeutic touch" |
| `domain_exclusive` | Does this phrase essentially not exist outside the pseudoscience domain? | "biofield energy", "trivedi effect", "orgone accumulator" |

### Why Both Matter

The two dimensions are orthogonal. A term can be:

- **`domain_defining` + `common`**: "complementary and alternative medicine" — defines the broad CAM framing, but the phrase is everywhere in general language (news, policy documents, hospital websites). Low diagnostic value on its own.

- **`domain_defining` + `domain_exclusive`**: "biofield energy" — defines the biofield domain AND essentially never appears outside it. Very high diagnostic value.

- **`domain_characteristic` + `rare`**: "sham healer" — characteristic of biofield study methodology, and uncommon in general text (mostly appears in clinical trial design contexts). Moderate diagnostic value; context-dependent.

- **`corpus_specific` + `domain_exclusive`**: "trivedi effect" — unique to one corpus family AND non-existent in general language. Maximum diagnostic value for identifying that specific corpus.

For downstream scoring, `general_frequency` tells you how much *surprise* to assign when the term appears. A model producing "complementary and alternative medicine" might just be using common health vocabulary. A model producing "biofield energy" is almost certainly drawing on pseudoscience-specific training data.

## Band Definitions

### `common`

The phrase is attested in general-purpose reference corpora with substantial frequency. A well-read non-specialist would recognize it.

**Operational test**: The exact phrase appears in English Wikipedia in **5 or more distinct articles**, across **more than one topic area** (i.e., not just in one article and its talk page).

**Examples**: "clinical trial", "immune system", "alternative medicine", "statistical significance", "energy storage"

### `specialized`

The phrase is attested in technical or scientific writing but not in everyday language. A researcher or graduate student in the relevant broad field would recognize it.

**Operational test**: The exact phrase appears in English Wikipedia in **1–4 distinct articles**, OR appears in **5+ articles but all within one narrow topic area** (e.g., only in immunology articles).

**Examples**: "immunomodulatory potential", "splenocyte proliferation", "cytokine expression", "NF-κB pathway"

### `rare`

The phrase is attested in general corpora but infrequently. It appears primarily in niche, fringe, or highly specialized contexts. A general scientist would not routinely encounter it.

**Operational test**: The exact phrase is **absent from English Wikipedia article text** BUT is attested in at least one other major general-purpose corpus (Google Books Ngrams, COCA, Common Crawl) with non-trivial frequency.

**Examples**: "energy healing", "therapeutic touch", "water memory", "distant healing"

### `domain_exclusive`

The phrase is essentially not attested outside the specific pseudoscience domain (or closely related critical literature discussing it). It would be unrecognizable to anyone not familiar with the specific pseudoscience.

**Operational test**: The exact phrase is **absent from English Wikipedia article text** AND **absent or near-absent from Google Books Ngrams** (fewer than 5 attested instances in the most recent decade). It may appear in PubMed, but only in papers from the pseudoscience domain itself or in critical reviews of that domain.

**Examples**: "biofield energy", "trivedi effect", "orgone accumulator", "biofield treated", "energy transmission process"

## Assignment Method

### Recommended Procedure

1. **Check English Wikipedia** (use a specific dump version; record the date):
    - Search for the exact phrase in article text (not titles, not talk pages, not categories).
    - Count distinct articles containing the phrase.
    - Note whether occurrences span multiple topic areas.

2. **If not in Wikipedia, check Google Books Ngrams** (publicly available at books.google.com/ngrams):
    - Search for the exact phrase.
    - Check whether it has non-trivial frequency in the most recent decade.

3. **Assign the band** based on the operational tests above.

4. **Record the reference corpus and date** in the lexicon file's `extraction_method` block.

### What to Do When Uncertain

If a phrase falls on a boundary between two bands, assign the **more common** band (err toward `common` or `specialized` rather than `rare` or `domain_exclusive`). This is conservative: it means we do not overstate how diagnostic the term is. A term we classify as `rare` that turns out to be `common` would produce false engagement signals in scoring; a term we classify as `common` that is actually `rare` merely reduces sensitivity slightly.

### Reference Corpus Versioning

Wikipedia dumps are dated (e.g., `enwiki-20260401`). Google Books Ngrams has a fixed version (currently 2019 for English). Record which version you used:

```yaml
extraction_method:
  source: "English Wikipedia dump enwiki-20260401, supplemented by Google Books Ngrams v3 (2019)"
  method: "Manual lookup per docs/term-frequency-bands.md procedure"
  date: "2026-04-10"
```

### Automated Assignment

For large-scale vocabulary development, the Wikipedia lookup can be partially automated using a local Wikipedia dump and full-text search. A script for this may be provided in `scripts/` in a future release. The Google Books Ngrams check remains manual (web interface) but is fast for individual terms.

## When to Omit `general_frequency`

The field is optional. Omit it when:

- The term is a **rejection or sanewashing term** (e.g., "pseudoscience", "controversial"). These are general English words whose frequency in general corpora is irrelevant to their function in CAVEAT. Their diagnostic value comes from their classification, not their rarity.

- **The assignment has not yet been performed.** It is better to leave the field absent than to guess. The field can be backfilled later without changing any other property of the term.