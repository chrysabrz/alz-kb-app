# Scoring and verdict rules

Every number and label in `06_knowledge_base.csv`, what it means, and where the thresholds
came from. Companion to [NOMENCLATURE.md](NOMENCLATURE.md), which covers drug names.

All of this is implemented in [`step6_build_kb.py`](step6_build_kb.py).

---

## The governing principle

**Every judgement is shown next to the fact it was derived from.**

A verdict label is an opinion. The counts and the ratio behind it are facts, and they are
on every row. A reader who disagrees with my thresholds can ignore the label entirely and
use the numbers.

---

## Counting: papers, not claims

One paper often makes several claims about the same drug. A study reporting that metformin
improved cognition, lowered amyloid and reduced inflammation is **one piece of evidence**,
not three.

So every count and score in the knowledge base is over **distinct PMIDs**. `n_claims` is
also recorded, but nothing is ranked by it.

---

## Study weights

Not all evidence is equal, and a drug should not climb the table on computer predictions.

| Study type | Weight | Why |
|---|---|---|
| clinical trial | 1.00 | people, with an intervention |
| meta-analysis | 1.00 | pooled trials |
| patient cohort | 0.70 | people, observed not assigned |
| case-control | 0.60 | people, retrospective |
| animal | 0.40 | a living organism, not a person |
| cells | 0.20 | no organism at all |
| computer prediction | 0.10 | no biology at all |
| review, other, unknown | 0.20 | cannot be placed |

These are a **crude proxy for study quality**, not a quality assessment. A bad trial still
scores 1.00 and a superb mouse study still scores 0.40. Nothing here reads the methods and
judges them.

---

## `helps_score` and `harms_score`

```
helps_score = sum of study weights over DISTINCT papers claiming "helps"
harms_score = same, for "harms"
```

They are kept **separate and never subtracted**. A net score would let 10 harms cancel 10
helps and produce a zero that looks like "no evidence", when the truth is "a lot of
evidence, violently disagreeing".

Drugs are ranked by `max(helps_score, harms_score)`, so a strongly harmful drug ranks as
prominently as a strongly helpful one. That is deliberate: anticholinergics raising
dementia risk is as important a finding as metformin lowering it.

### What the score is not

- **Not a probability the drug works.** It measures how well evidenced a claim is.
- **Not an effect size.** A drug with a huge effect in one trial scores 1.00, the same as
  a drug with a trivial effect in one trial. Use the `effect_size` column for magnitude.
- **Not comparable across very different corpora.** It depends on how many papers happened
  to be retrieved.

A drug studied once in a trial outranks one studied five times in cell culture. That is
intended.

---

## The ratio

Every row carries the exact balance in two forms:

| Column | Example | Meaning |
|---|---|---|
| `helps_harms_ratio` | `74:8` | papers saying helps, papers saying harms |
| `ratio_value` | `9.25` | the same as a number; blank when there are no harms |

**This is the fact. The verdict below is only an interpretation of it.**

---

## Verdicts

| Verdict | Condition |
|---|---|
| `helps (multiple papers)` | 2+ helps, **zero** harms |
| `helps (single paper)` | 1 help, zero harms |
| `helps (minority dissent)` | both, and **ratio >= 4.0** |
| `CONTRADICTED` | both, and ratio between 0.25 and 4.0 |
| `HARMS (minority dissent)` | both, and **ratio <= 0.25** |
| `HARMS (multiple papers)` | 2+ harms, zero helps |
| `HARMS (single paper)` | 1 harm, zero helps |
| `no effect found` | only `no_effect` claims |

### Where the 4:1 threshold came from

**It was set after looking at the data, not before**, and the first version was wrong.

The original rule was simply *any helps AND any harms → CONTRADICTED*. That produced:

| Drug | helps | harms | ratio | labelled |
|---|---|---|---|---|
| Metformin | 74 | 8 | 9.2 | CONTRADICTED |
| Minocycline | 46 | 1 | 46.0 | CONTRADICTED |
| Liraglutide | 33 | 1 | 33.0 | CONTRADICTED |
| Anticholinergics | 1 | 44 | 0.02 | CONTRADICTED |

**Of 69 drugs marked CONTRADICTED, 26 were in fact lopsided.** Metformin at 74-to-8 is a
strong positive with minority dissent; anticholinergics at 1-to-44 is clearly harmful.
Calling both "contradicted" misrepresents the literature, and it buried the single
best-evidenced candidate in the corpus.

With the 4:1 threshold, 43 drugs remain genuinely `CONTRADICTED`, 23 become
`helps (minority dissent)` and 3 become `HARMS (minority dissent)`.

**4.0 is a choice, not a discovery.** It is round, it separates the observed cases
sensibly, and it is one constant (`DISSENT_RATIO`) at the top of the file. Change it and
re-run; the ratio column means you do not have to trust it.

---

## `best_evidence`

The strongest study type any paper about this drug used, ranked:

```
clinical_trial > meta_analysis > patient_cohort > case_control >
animal > cells > computer_prediction > review > other
```

It is the **ceiling, not the average**. A drug whose `best_evidence` is `clinical_trial`
has at least one trial; it may have twenty mouse studies as well.

---

## Full-text fields

`effect_size`, `sample_size`, `duration`, `comparator`, `dose_achievable`,
`brain_penetrant` come from [`step5b_add_details.py`](step5b_add_details.py) and are only
available for papers in PubMed Central's open-access subset, about **51%** of this corpus.

When several papers cover one drug, the value is taken from the **strongest study**, and
`_pmid` records which paper it came from.

**A blank field means "we could not read that paper", not "the paper reported no dose".**
Those are different, and conflating them would overstate how much is unknown.

Fill rates, of 921 (paper, drug) pairs sent:

| Field | Filled and quote-verified |
|---|---|
| comparator | 55% |
| effect_size | 46% |
| duration | 38% |
| sample_size | 32% |
| dose_achievable | 29% |
| brain_penetrant | 22% |

`brain_penetrant` being lowest is itself a finding: most of this literature never addresses
whether the drug reaches the brain.

---

## Alzheimer's drugs are separated, not deleted

Donepezil, memantine, rivastigmine, galantamine, tacrine, aducanumab, lecanemab, donanemab
and brexpiprazole are already licensed for Alzheimer's. They are **not repurposing
candidates**.

They are kept as the **positive control**: the pipeline found all nine on its own, without
being told to look for them. If it had not, nothing else in the table could be trusted.

They sit in their own section, flagged `is_alzheimers_drug`.

---

## Unresolved drugs

A drug that matched nothing in the dictionary keeps its own row under the name the paper
used, prefixed `UNMATCHED:`. It is never merged with another drug on a guess.

562 of 1,056 rows are resolved to a database ID. The remainder are mostly research codes
(`NP03`, `compound 11e`), herbal formulas, and things that are not drugs at all.

---

## Known limits

1. **Study weights are a proxy**, not a quality assessment. Nothing reads a paper's methods.
2. **The corpus shapes the scores.** These are relevance-ranked PubMed searches, not a
   systematic review, so counts reflect what was retrieved.
3. **Publication bias is inherited.** Null results are under-published, so `no_effect` is
   certainly undercounted.
4. **A verified claim is not a true finding.** The pipeline checks that a paper said
   something and that the quoted sentence supports it. It does not check whether the paper
   is any good.
