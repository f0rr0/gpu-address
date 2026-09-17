# Website benchmark audit — 2026-09-17

This audits the former Senzing-based website chart. The website now uses the
[public-address evaluation](apps/website/public/evaluation-v4/README.md), with
NAD and Companies House inputs, per-field scores and separate UK county groups.
The former institutional diagnostic remains at `apps/website/public/evaluation/`.

The published counts reproduce, but the country chart does not establish general
accuracy superiority. The strongest supported positioning is a small, local,
experimental parser with narrower coverage and uneven generalization.

## Verification

- Independently implemented the scorer using only Python's standard library,
  without importing the training scorer or schema. All published per-country
  counts, shared-subset counts, prediction hashes and source CSV hash match.
- Reran Deepparse 0.10.0 BPEmb + attention on all 3,151 inputs with the existing
  downloaded checkpoint: zero changed predictions. Also reproduced three examples
  individually and together, including UK and Irish failures.
- Reviewed the benchmark harness, raw predictions, field mapping, corpus language
  selection, size manifest, model card, and upstream documentation/paper.
- This is an independent implementation check of existing evidence, not an
  independent third-party evaluation or a new blind test. Other parsers were
  rescored from cached predictions, not rerun. Size compression and browser
  performance measurements were not rerun in this audit.

Reproduce the score audit:

```sh
python3 packages/training/scripts/audit_website_benchmark.py
```

## Results

Counts require every field to match. Shared fields are street address, city,
state and postcode; complete means all four present and no other gold fields.

| Input subset | Rows | gpu-postal | libpostal | Senzing | Deepparse |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 3,151 | 2,850 (90.4%) | 2,975 (94.4%) | 3,093 (98.2%) | 1,427 (45.3%) |
| Shared fields only | 2,664 | 2,475 | 2,532 | 2,619 | 1,427 |
| Complete shared fields | 1,460 | 1,427 (97.7%) | 1,446 (99.0%) | 1,451 (99.4%) | 1,423 (97.5%) |
| Partial shared fields | 1,204 | 1,048 | 1,086 | 1,168 | 4 |
| Complete Canadian subset | 31 | 5 | 30 | 30 | 30 |

The complete subset is 1,427 US, 31 Canadian, one UK and one Australian input.
It cannot establish worldwide parity either. The four-address advantage over
Deepparse is not evidence of a meaningful general lead.

## Why Deepparse looks so bad

487 inputs contain gold fields absent from its label vocabulary. They cannot
pass this exact-match comparison. The shared-field switch removes that mismatch
but still mixes complete and partial addresses.

Deepparse fails 1,200 of the 1,204 partial shared-field inputs. An inspected UK
example, `318 Upper Street, N1 2XQ London`, has the street and postcode correctly
assigned but labels London as Province. This is a real prediction error, yet the
whole-address metric awards zero for the entire address. The Canadian chart's
31/432 hides 30/31 on complete inputs and 1/387 on partial shared-field inputs.

Deepparse's paper measures the proportion of correctly predicted tags per
sequence, not our all-fields-or-zero metric. Its published high percentages
therefore do not conflict directly with these results. Its documentation also
separates clean and incomplete inputs. Only BPEmb + attention was tested here;
these results do not characterize all Deepparse models or fine-tuned versions.

Sources: [evaluation procedure](https://arxiv.org/html/2006.16152),
[Deepparse data categories and country results](https://deepparse.org/).

## Other limits on the claims

- The Senzing set was inspected during development. Neither its publisher nor
  our prior use makes it a neutral blind ranking. Competitor training overlap
  remains unknown. See [Senzing's benchmark repository](https://github.com/Senzing/libpostal-data).
- Seven-field scoring collapses road, house number, unit and premises into one
  street field. Token multisets ignore within-field order. These are useful
  application semantics, but not validation of every native parser label or span.
- The model card's separate GeoSearch result already shows Deepparse ahead on
  complete inputs: 741/770 versus our 714/770. Those saved results were not rerun
  here; they reinforce the need to separate input types.
- The size advantage is credible from the asset inventory, but the comparison
  covers differently scoped systems. libpostal includes normalization/language
  resources; Deepparse includes multilingual embeddings. The page's numbers are
  Brotli quality 5 data assets, not memory, installed size or total runtime.
  The README uses quality 11 model plus JavaScript, explaining its different size.
- The 99.17% holdout result is same-source evidence, not external accuracy.
- Training selection accepts English-tagged records and generated-from-fields
  records with no language tag. “English-form addresses from seven countries”
  is more precise than asserting every record is verified English-language.

## Recommended presentation

Keep the compact experimental/browser/size pitch. Rename the comparison to
“Senzing development set” and make “whole-address exact match” visible. Separate
complete and partial shared-field results, with counts. Keep seven-field coverage
results separate from a like-for-like comparison; do not replace the current
chart with only the favorable complete subset. Label the size comparison as
compressed data assets with differing language/function coverage.

Before claiming competitive accuracy generally, freeze the models and scoring,
then evaluate a new independently annotated sample balanced by country and input
completeness. Report field-level scores alongside whole-address exact match.
