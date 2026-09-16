# gpu-postal seven-country release

17 September update: training is complete; epoch 12 int8 is frozen for
`0.1.0-experimental.1`. See the [current model card](../MODEL_CARD.md) and
[actual-browser release check](evidence/release-qualification-20260917.json).

Requested 16 September 2026. This reopens training for a narrower release and
supersedes the no-further-training decision in `closeout.md`. The worldwide
retrospective remains historical evidence, not a prohibition on this new request.

## Contract

US, UK, Australia, New Zealand, Canada, Ireland and English-language South African
addresses. The user confirmed these seven countries. Retain proper names, including
non-English names in English-form addresses. Do not claim general multilingual or
worldwide coverage. Retain the existing seven output fields and H128 WebGPU model.

## Training and selection

Prepared corpus: **3,790,046 training rows**, 12,124 validation rows and 12,115
sampled test rows. Full heldout partitions are retained separately. English/unknown
language filtering excluded 9,491 candidate occurrences; deduplication identified
3,189 repeats and quarantined 1,835 conflicting normalized-text keys.

| Country | Training rows | Validation | Test sample |
| --- | ---: | ---: | ---: |
| US | 77,917 | 2,000 | 2,000 |
| UK | 74,191 | 2,000 | 2,000 |
| Australia | 1,297,093 | 2,000 | 2,000 |
| New Zealand | 1,415,622 | 2,000 | 2,000 |
| Canada | 2,225 | 124 | 115 |
| Ireland | 50,883 | 2,000 | 2,000 |
| South Africa | 872,115 | 2,000 | 2,000 |

Canada's small reservoir is a release limitation, not repaired by loss weighting.
The pipeline ran under `caffeinate -i`; its log is
`runs/english-seven-20260916.log`. All 12 epochs completed in 13,772.94 seconds.

- Prepare all usable existing admitted originals from diagnostic-v4 plus the approved
  US/UK expansion. Do not reuse balanced-v5's materialized repetitions or cap training
  at a pilot sample. This is not acquisition of every raw source shard.
- Retain source-declared English and language-neutral generated-field inputs. Exclude
  explicit other-language renderings and unclassified tagged rows; record counts.
- Preserve previous evaluation protections. Deduplicate case/whitespace-normalized
  text, quarantine disagreements, and split street/locality groups 90/5/5 into
  train/dev/test. Keep all heldout rows; use a fixed reservoir of at most 2,000 rows
  per country per evaluation split for practical epoch scoring.
- Train **from scratch**, not a parent that has seen the newly heldout groups.
  Full shuffled training pass each epoch, MPS, batch 128, seed 2026, case augmentation.
  Inverse-frequency country loss weights give every country equal total objective
  weight while retaining all training rows. This is an explicit product-priority
  choice, not a proven optimal recipe; rare countries still have limited diversity.
- Initial LR 0.001; halve on a validation plateau; stop after three plateau epochs,
  with a 12-epoch safety budget. Select by equal-country mean exact ordered-span
  validation accuracy. An exhausted budget while still improving is not convergence.
- Do not tune on the test split or public benchmark. After selection, evaluate the
  heldout split and the existing public/natural diagnostics by country, including
  denominator and exact metric. Earlier checkpoints' new-source-holdout results
  are exposure-confounded; compare them on the old protected diagnostics instead.

## Qualification and publication

Completed qualification/review: [epoch-12 candidate review](evidence/english-seven-final-review-20260916.md).
Actual Apple Metal WebGPU fixture parity passed for both exports. Epoch 12 int8 is
the nominated research artifact. Original code is now MIT; model source notices
and restrictions are preserved separately. The run
ended at its epoch budget while validation was still improving, not convergence.

Export the selected checkpoint in GPA3 float32 and int8. Verify quantization quality,
existing tests, and actual browser WebGPU parity on the exact exported artifact.
Preserve hashes, training source, data manifest and completion reason. Do not replace
the prior nominee merely because the new run is newer; inspect country tradeoffs.

Publish one qualified research candidate on the existing GitHub repository, with
measured country results and honest limitations. No new website, npm workflow,
architecture sweep or data-collection campaign. Never publish raw training corpora.

The user authorized MIT for original code on 17 September and explicitly approved
publishing weights with source notices/restrictions preserved. See
[third-party notices](../THIRD_PARTY_NOTICES.md). Do not describe the entire bundle
as unrestricted MIT. No raw corpus is published.

## Reproduction

```sh
uv run python docs/evidence/prepare-english-seven-20260916.py --output data/english-seven-20260916
uv run gpu-postal train --data data/english-seven-20260916 --run runs/ordered-h128-english-seven-20260916 --device mps --batch-size 128 --epochs 12 --lr 0.001 --seed 2026 --case-augmentation --country-balanced-loss --selection-metric country_macro_accuracy --patience 3
```

The actual unattended pipeline is `uv run python docs/evidence/run-english-seven-20260916.py`:
it runs that training command, then frozen test evaluation, float/int8 export and
existing protected diagnostics and JavaScript parity. It does not publish automatically.
The recorded run IDs remain unchanged after renaming the project to gpu-postal.

Validation performed before launch: the Python test suite and browser-package tests
pass; maintained Python package/tests pass Ruff and type checking. Repo-wide checks
also scan historical evidence scripts, which have existing lint/type/format issues;
those scripts were not bulk-rewritten during this training task.

Same-source heldout streets are not representative natural user traffic. Incomplete
entity linkage, source-label mistakes and small-country data deficits remain. Report
them rather than calling the model fully accurate in a country.
