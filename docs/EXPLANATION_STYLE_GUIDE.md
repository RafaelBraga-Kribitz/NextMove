# Explanation Style Guide

Every `Decision` carries a `reasoning` paragraph a marketing manager can read without edits
(QUALITY_BAR AC-4, O5). This guide is the contract for that paragraph. It is enforced by code:
`src/nextmove/explain/templates.py` is the only place the text is produced, and
`tests/unit/test_explanations.py` scans generated explanations for prohibited phrasing.

## How explanations are produced

- **Templated, never generated.** No language model is in the explanation path
  (anti-pattern 2). Each sentence is a fixed template filled from fields of the structured
  `reasoning_trace`, so the paragraph cannot claim anything the trace does not contain
  (faithfulness).
- **Order of sentences:** recommendation → expected effect (or why restraint wins) → main
  factors → rules that ruled options out or reduced scores → confidence.

## Rules

1. **Lead with the recommendation.** The first sentence always starts with
   `Recommendation:` and names the action in catalog language ("Small discount code (10% off)").
2. **Relevance, not surveillance.** Describe *why the customer's situation matters*, not what
   they did when. Allowed: "their history of buying on discount", "how many messages they have
   received overall", "items waiting in their basket". Prohibited: clock times, dates of
   individual visits, product or session identifiers, "you viewed / we tracked you",
   raw event names. (Anti-pattern 10.)
3. **Say why restraint wins.** When the engine does nothing, name the best active alternative
   and its expected effect and profit, or state that every contact option is ruled out by the
   rules.
4. **Name the decisive constraint.** Every rule that removed options is listed with the number
   of options it removed; soft penalties that reduced the chosen option's score are named.
5. **State uncertainty.** Model-based decisions report a plausible range for the effect and a
   confidence (the share of model resamples that rank the option first). If confidence is below
   the configured threshold the engine falls back to doing nothing and says so. Rule-based
   policies say they have no confidence score instead of inventing one.
6. **Plain units.** Effects in percentage points of purchase chance, money in euros with sign,
   percentages rounded to whole numbers.
7. **No promises.** Never "will buy"; use "expected to change their purchase chance".

## Feature phrases

The mapping from model features to phrases is `FEATURE_PHRASES` in
`src/nextmove/explain/templates.py`; a test fails if a model feature has no phrase.

## Review rubric (QUALITY_BAR §6)

Sampled decisions are scored 1–5 on faithfulness, completeness, readability, framing and
honesty; release requires a median ≥ 4 with no faithfulness score below 3. The golden file
`tests/golden/fixtures/decisions_golden.jsonl` holds the reference sample.
