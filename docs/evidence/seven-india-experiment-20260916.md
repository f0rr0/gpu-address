# Seven-label India experiment — 16 September 2026

Status: **training and evaluation complete; reject promotion of the new-data recipe.**
This is a bounded data-content experiment, not release qualification or final retraining.

## Decision and measured result

The recovered batch did not deliver a useful fresh-source gain: **35/168 versus 34/168**
for the matched control (four wins, three losses). It improved the older India pilot by
six addresses but lost 24 public addresses overall. Do not scale this Assam-heavy
mixture, call it a nationwide improvement, or launch final retraining on its strength.

| Slice | Old case-v6, projected to seven | Seven-label control | New-data treatment |
| --- | ---: | ---: | ---: |
| Fresh India business addresses | 28/168 | 34/168 | 35/168 |
| Existing India pilot | 61/359 | 55/359 | 61/359 |
| Public India | 27/54 | 29/54 | 29/54 |
| Public US | 1922/2233 | 2027/2233 | 2009/2233 |
| Public UK | 220/255 | 228/255 | 225/255 |
| Public South Africa | 43/53 | 31/53 | 28/53 |
| Public New Zealand | 43/51 | 35/51 | 33/51 |
| Public Australia | 24/76 | 20/76 | 20/76 |
| Public Singapore | 49/50 | 46/50 | 48/50 |
| Natural priority subset | 47/55 | 45/55 | 47/55 |

The same frozen fresh India set scores **57/168 with libpostal-Senzing**. These are
agreement counts under one seven-field metric on AI-reviewed convenience samples,
not published F1 or population-wide accuracy. Senzing's unknown training exposure and
the public set's pre-existing selection/exposure limitations remain.

Treatment versus control paired wins/losses: fresh India 4/3; India pilot 10/4;
public India 0/0; US 14/32; UK 4/7; ZA 2/5; NZ 1/3; AU 1/1; SG 2/0;
natural subset 2/0. Exact ordered spans also barely change on fresh India: 30/168
control versus 31/168 treatment. On the older pilot: 55/359 versus 59/359.

Both arms completed one epoch with 128,000 supported training presentations, zero
rejections, identical parent/code/optimizer settings and case-augmentation choices.
Training time: control 120.56 seconds; treatment 114.86 seconds. Source-dev ordered
exact: 1828/2048 versus 1830/2048. This small dev difference is not a reason to
override the country regressions. There is one seed, not a replicated effect estimate.

### Next action, without another architecture detour

**Superseded by project closure on 16 September 2026.** The recommendations below
were not started; follow the [publication plan](../closeout.md) instead.

Keep the seven-field product contract and existing checkpoints; do not promote either
short continuation as a final model. The encoder-transfer recipe has not preserved
the old ZA/NZ behavior, even though US/UK improve.

Before buying more training time, repair the India exposure/data mix:

1. Use the existing corpus to measure and correct the share of complete street-bearing
   India examples versus administrative-only fragments. A quick profile of this
   experiment's existing India reservoir finds street_address in only 1,851 of 3,914
   exact-text-unique rows (3,911 after normalized-text dedup). This is a reservoir
   observation, not a census of the entire corpus or proof of the failure's cause.
2. Build the next annotation tranche from multiple states and address forms, not more
   of this Assam company-register tail. Reuse the pinned raw reservoir; prioritize
   usable premises/locality/city/state boundaries, full state names, apartments,
   commercial addresses and rural/post-office forms. Retain rather than guess
   unresolved concatenations. The current 259 remain usable source evidence, not a
   representative training distribution.
3. Run the next bounded comparison only after that distribution change is material.
   These already-inspected diagnostics are now development evidence; reserve new
   source/entity-separated examples for a later release decision. A full seven-label
   retraining run remains necessary before release, but calling it "final" now is premature.

Completed scripts: `prepare-seven-experiment-20260916.py`,
`prepare-seven-pair-20260916.py`, `evaluate-seven-20260916.py`, and
`evaluate-previous-india-seven-20260916.py`. Per-input predictions and input/checkpoint
hashes are retained in each run's `frozen-evaluation/` directory and
`data/india-seven-20260916/previous-comparators/`.

## Fixed protocol

- Seven fields: street_address, locality, city, district, state, postcode, country.
- Existing H128 backbone, MPS on the M1 Pro; no new architecture or dependencies.
- Baseline: old case-v6 epoch-1 encoder, fresh seven-label output/CRF; two epochs on
  256,000 uniformly selected balanced-v5 presentations, seed 2026, batch 128,
  learning rate 0.001, existing case augmentation. All original corpus rows remain retained.
- Shared development set: 2,048 existing source-dev rows; no pilot/public checkpoint selection.
- Paired arms: same baseline best checkpoint, fresh AdamW, learning rate 0.0003,
  seed 2026, batch 128, case augmentation, **one epoch each**.
- Each arm: 121,600 identical existing presentations plus 6,400 India presentations.
  Control India slots use existing India data; treatment slots use newly admitted labels.
  Same presentation count and country counts; input lengths and elapsed compute can differ.
- The original 20% replacement proposal was reduced to 5% before either arm ran:
  the recovered batch is only a few hundred rows. This remains deliberate repeated exposure,
  not a claim that 5% is optimal. Report unique rows and actual repeats separately.
- Freeze corrected fresh evaluation labels before any predictions on that set.
  The old 359-row India pilot remains untouched and excluded from training.
- Report all existing priority-country slices plus the fresh India business-address set;
  compare paired wins/losses rather than hiding country regressions behind an overall score.

## Data findings that constrain the conclusion

The projected gold-source tranche initially contained 253 addresses, **all from Assam**.
Root's additional sample found locality text incorrectly retained inside street spans;
the complete tranche was then individually reviewed: 232 accepted, 21 held, 40 boundary
corrections. The source's `REVIEWED_CORRECTED`
status and exact-offset checks were insufficient semantic guarantees.

Raw recovery initially yielded 12 sentinel/boundary repairs and 15 accepted fresh reviews
from 50 candidates. Ambiguous rows remain held. Final deduplication/entity/protection gates
retained all 259 accepted rows, with no additional duplicate/protected exclusions.
Of these, 235 have state `AS`: **90.7% of the new batch is Assam**. This does not meet
the original ambition of thousands of diverse
new India examples, and must not be described as a nationwide data expansion.

Fresh evaluation is a four-brand business/store convenience sample, not residential
coverage or representative India accuracy. Primary labels required substantive corrections
(including postal codes and cities misassigned to street address). Preserve the original
primary annotations, corrections, held rows and frozen-input hashes.

Final frozen set: **168 accepted / 200 candidates**, 32 unresolved holds, no overlap
detected by the recorded base text/model/street/source-entity gates. All accepted labels
are representable by the existing tokenizer. Locked input SHA-256:
`0c421956e26bb623d207c729109a54be762cf739dafc745e206fb02940f0bcee`.
The final root corrections preceded every fresh-set prediction; no further label changes
are permitted within this comparison. The seven-label baseline gets 16/168 exact here.

Both arms contain 8,620 India presentations including the identical shared examples.
The treatment's 6,400 replacement slots expose each of its 259 new rows 24–25 times.
The old-India sampling reservoir has 4,659 presentations and 3,911 unique normalized texts.
Country and update budgets are matched; within-India geography/source diversity is not.

## Baseline evidence

The seven-label baseline finished in 343.68 training seconds; source-dev selected epoch 2
(1,816/2,048 exact ordered spans). The frozen 3,186-row diagnostics returned:

| Slice | Correct / total |
| --- | ---: |
| Public US | 1,982 / 2,233 |
| Public UK | 222 / 255 |
| Public South Africa | 24 / 53 |
| Public New Zealand | 22 / 51 |
| Public India | 29 / 54 |
| Public Australia | 17 / 76 |
| Public Singapore | 45 / 50 |
| India pilot | 46 / 359 |
| Natural priority subset | 44 / 55 |

Metric: exact seven-field token multisets, ignoring case, whitespace, commas and order;
duplicate token counts remain significant. Exact ordered spans are separately available
where source offsets exist. Public labels do not have source offsets.

This baseline is **not a release candidate**: compared with the previous model's seven-field
projection, US/UK are slightly better but South Africa/New Zealand regress sharply.
This tests a short encoder-transfer recipe, not whether full seven-label training can work.
The controlled arms still isolate the effect of the small new label batch from that starting point.

Reproducible evidence lives in `runs/ordered-h128-seven-v7-base-20260916/diagnostics/`;
data and run directories are gitignored local artifacts. Preparation and scoring scripts
are retained next to this report. No checkpoint has been promoted.

## Runtime checks

All 30 Python tests and four browser-package unit tests pass. Both exported encodings
pass all 29 fixtures in JavaScript and on Chrome's non-fallback Apple Metal-3 WebGPU
adapter. Mixed-fixture warm median: 3.2 ms float32, 2.5 ms int8; this is not a
representative latency benchmark. The baseline int8 binary is 154,562 bytes, or
128,462 bytes when Brotli-compressed. [Browser evidence](seven-baseline-webgpu-20260916.json).

The export command produced working binaries/fixtures but its complete evaluation report
did not finish: the bounded training directory has no public-benchmark file. Do not
mistake the parity check for completion of that command or accuracy qualification.
An additional scoring migration fix makes the standard export/diagnosis paths compare
seven-field token content on both sides instead of seven-label predictions against
unchanged twenty-label gold. Legacy libpostal parsing and scoring remain unchanged.
