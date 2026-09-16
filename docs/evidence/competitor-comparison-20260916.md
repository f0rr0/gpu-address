# Existing-parser comparison — 16 September 2026

## Decision

Do not run another unchanged full-corpus training job or switch to Deepparse. Keep H128 epoch 1 as the current reference. The next cheap experiment should address missing administrative fields and multiword localities; use Senzing as an offline reference, not an unquestioned India labeler. These results do not establish that H128 lacks capacity or that distillation will work.

## Actual results

All parsers received the same 3,186 inputs without country hints. Full-field exact means every field's content matches after NFKC, case folding and whitespace normalization; it is not token accuracy or span exactness.

| Existing public slice | Rows | H128 epoch 1 | H128 epoch 2 | libpostal/Senzing |
|---|---:|---:|---:|---:|
| US | 2,233 | 79.9% | 79.1% | 95.9% |
| UK | 255 | 65.5% | 64.7% | 78.0% |
| South Africa | 53 | 58.5% | 45.3% | 66.0% |
| New Zealand | 51 | 84.3% | 52.9% | 98.0% |
| India | 54 | 16.7% | 16.7% | 33.3% |
| Australia | 76 | 28.9% | 18.4% | 98.7% |
| Singapore | 50 | 78.0% | 72.0% | 98.0% |

Separate AI-reviewed diagnostics, not pooled into the public result:

- India pilot: H128 epoch 1 **47/359**, epoch 2 **38/359**, Senzing **49/359**. Senzing wins 21 cases that epoch 1 loses, but loses 19 that epoch 1 wins; both fail 291.
- Natural priority-country subset: epoch 1 **43/55**, epoch 2 **42/55**, Senzing **46/55**. Forty-two rows are US; the other country samples are too small for conclusions.
- Public paired comparison: Senzing fixes 488 epoch-1 failures; H128 fixes 16 Senzing failures.

### Deepparse

Tested released Deepparse 0.10.0 BPEmb+attention, upstream preprocessing, CPU, no fine-tuning. Native labels and outputs are retained. Its narrower schema prevents a fair full-contract comparison. Mapping StreetNumber/StreetName/Orientation/Unit/Municipality/Province/PostalCode to our six corresponding fields, and ignoring commas equally for every parser, gives:

| Public rows requiring only those six fields | Rows | H128 epoch 1 | Senzing | Deepparse |
|---|---:|---:|---:|---:|
| US | 1,939 | 82.2% | 98.8% | 67.3% |
| UK | 125 | 96.0% | 98.4% | 0.0% |
| South Africa | 27 | 85.2% | 88.9% | 0.0% |
| India | 34 | 26.5% | 47.1% | 0.0% |

These are restricted, easier slices, not overall product accuracy. The NZ/AU/SG common-only samples contain just 2/7/6 rows. Deepparse also scores 0/55 natural and 1/359 India-pilot full-field matches. Single-input checks reproduce obvious mistakes: it labels London as Province in `318 Upper Street, N1 2XQ London`. This is evidence against adopting this released checkpoint for our inputs, not a claim that every Deepparse configuration performs this way.

## What the failures tell us

US examples without a state are a concrete weakness: epoch 1 gets **347/554 (62.6%)**, versus Senzing **520/554 (93.9%)**. With a state, scores are **1437/1679 (85.6%)** versus **1621/1679 (96.5%)**. This association does not by itself prove the training cause.

A seeded eight-case review of public Senzing wins found straightforward H128 errors: `new haven`, `south daytona` and `groveland` became states; `forest grove` and `red oak` were split across administrative labels; an unmarked unit and a house-number suffix were absorbed into roads. These are not merely gold-label disputes.

A seeded five-case review of joint India failures showed mixed problems: unit/building/locality distinctions, repeated administrative names, abbreviation handling, and genuinely difficult directory strings. The reference sometimes imposes questionable choices (e.g. Andaman Islands as state_district). Public gold also sometimes normalizes text beyond extraction: input `Tamilnadu` versus gold `tamil nadu` prevents even a correctly labeled extraction from matching. No labels were changed after seeing predictions.

## Next experiment, bounded

1. Inspect the existing generator for missing-state and partial-address coverage; use existing labeled records to add valid omitted-field forms while preserving multiword locality boundaries. No new source hunt.
2. Compare that single data change with the unchanged H128 baseline at equal training exposure. Use development data for checkpoint selection, not the public diagnostic table. Do not promote epoch 2 simply because it trained longer.
3. If this does not materially improve missing-field cases without country regressions, test a modestly larger compact model with the same data and budget. Do not assume size is the cause yet.
4. Keep India as a separate unresolved data/schema problem. Senzing's 49/359 does not justify bulk India pseudo-labeling. Do not claim production readiness for India or South Africa.

## Reproduction and limits

Runner: `docs/evidence/compare-parsers-20260916.py`; modes `prepare`, `h128-epoch1`, `h128-epoch2`, `deepparse`, `libpostal-senzing`, `score`. Outputs intentionally refuse overwrites. Frozen inputs, source hashes, model hashes, raw predictions, paired outcomes and counts are under `data/competitor-comparison-20260916/`.

libpostal revision `25099c506612b34b23b1bfe286ca6321fcf06f35`, Senzing parser v1.2.0, base/language data v1.1.0. Deepparse HF snapshot `4af74dad1d547804dfc2de8f40fb23fbbec5b811`; model and BPEmb asset hashes are in its metadata. Both H128 checkpoint hashes and frozen-source checks are recorded. Tools/models are isolated under `data/competitor-tools-20260916/`; Homebrew automake/libtool were installed for the native build. Project training dependencies were unchanged.

This is diagnostic evidence, not an independent release benchmark: Senzing maintainers used the public dataset, competitor training overlap is unknown, H128 has repeatedly been evaluated on it, and the natural/pilot labels are AI-reviewed. There is one repeated text among the 3,186 rows; results retain the existing source weighting. Country samples are unequal and several are tiny. No worldwide accuracy claim, browser speed comparison, or causal capacity conclusion is warranted.
