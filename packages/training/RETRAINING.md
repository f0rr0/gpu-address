# US-only robustness run — 2026-09-17

Supersedes the seven-country recipe. The released model stays untouched.
Use the existing h128 byte-CNN/bidirectional-scan/CRF, seven-field API and int5
export. Enable existing gap features consistently in training and WebGPU.
No architecture sweep, new dependencies, teacher, gazetteer or source collection.

## Data

- Reuse all **3,077,917 US originals** from the frozen
  `data/robustness-int5-20260917` selection. Preserve IDs, source subspans and
  train/dev/test membership. No remaining shard or Texas scans.
- New output: `data/us-robustness-int5-20260917`. Parent hashes and counts checked.
- Full training is disk-backed on the M1 Pro. No CPU thread override.
- Pilot only: deterministic seed-2026 reservoir of 200,000 training originals.
  This approximates the selected corpus distribution, not equal state quotas.
- Retain separate old-US/new-US clean panels. Freeze partial, reordered,
  combined and explicit ZIP-first dev/test panels before training. Up to 1,000
  parent groups per synthetic panel; no-op exclusions reported.
- The existing 20 US AI-authored challenge examples and upstream usaddress US50
  test examples are final diagnostics, never checkpoint selectors or training.
  US50 source XML and license copied locally; exact train overlap reported.
  Historical source-curated examples are not new human gold or representative
  natural traffic; competitor exposure and entity overlap remain unknown.

## Training distribution

Per presentation: 50% original, 25% partial, 15% reordered, 10% combined.
Keep existing case augmentation independently. Log actual modes and fallbacks.

Partial operations: omit country/postcode/state/district/locality; retain street,
street+city, city+state or city+postcode; remove unit/floor, building or number
only where original fine source spans establish the boundary. No generated bare
house numbers or ambiguous standalone names. Original one-field examples remain.
Training-only ambiguity index rejects conflicting reduced inputs; no test labels
are consulted. The pilot shares the full-training ambiguity exclusions.

Reorder intact blocks: street-last, ZIP-first, reverse administrative blocks or
nonidentity shuffle. Also permit unit-first when fine spans project exactly to
the original coarse spans. No invented internal boundaries. Combined mode drops
fields before reordering; fine-only unit movement may fall back after deletion.
Rendered boundaries use space, comma-space or newline equally. Keep internal
punctuation intact; regenerate and verify spans. Unannotated words cannot vanish.

## Pilot gate (declared before training)

Fresh random initialization, seed 2026, AdamW LR .002, weight decay .01,
batch 128, MPS, h128, gap features, int5 evaluation each epoch.
At most 24 epochs or two hours, finishing an active epoch. After epoch 12,
six stagnant epochs stop training. Halve LR after two stagnant epochs,
floor .00001. Full-run settings are identical except its larger corpus and budget.

Select checkpoints by mean partial/reordered/combined int5 exact-span accuracy,
subject to clean accuracy within 0.5 percentage points of the released baseline
and at most max(ceil(1% of rows), 1) additional errors separately on old/new-US.
Tie-break on clean accuracy then earlier epoch. Epoch selection does not use test.

Start full training only if this selected pilot checkpoint also meets:

- Reordered error reduction >=10% versus release.
- ZIP-first accuracy >=80% AND >=10% error reduction versus release.
- Partial and combined accuracy within 0.5 percentage points of release.
- All clean guards above.

These are engineering go/no-go thresholds, not statistical significance claims.
A failed short pilot blocks automatic continuation; inspect its learning curve
before diagnosing an architecture ceiling. Do not silently weaken the gate.

## Full run and review

Start **from scratch**, not pilot weights. All 3,077,917 originals are eligible
every epoch, shuffled. Up to ten hours; no arbitrary epoch cap. Same plateau/LR
rules. Predict next-epoch duration from the slowest of the last three epochs;
do not start one projected beyond budget. Report time-budget versus convergence.
Keep each epoch checkpoint and metadata; select only on int5 dev results.

After training, evaluate the selected checkpoint once on frozen test panels:
same clean/reordered/ZIP-first guards; partial error reduction >=10%; combined
and new-US clean must not regress. US50 and AI challenge exact matches must not
decrease. Failure stops release, not another search through test checkpoints.
Compare against usaddress on the exact same inputs with the existing coarse-field
token scorer; also report our stricter exact-span score separately.

Candidate model-only transfer budget: <=72,467 bytes (Brotli quality 11), 5% above
the released 69,016 bytes (Brotli). US-only scope does not reduce parameter count.
An h96 experiment is deferred until this recipe demonstrates useful robustness.

Then use existing browser qualification with the private candidate artifact:
int5 Python/WebGPU parity, original UTF-16 spans, gap/newline/reordered regressions,
GPU failures, model+runtime transfer size (Brotli), warm median/p95 latency.
Require <=10% reproducible latency regression. Do not publish or overwrite the
package model automatically. Browser checks remain a separate release gate.

## Execution

`python packages/training/scripts/run_robustness.py` runs tests, US preparation,
panels/baselines, pilot, pilot gate, full training, then candidate test review.
Use `.venv/bin/python` under `caffeinate` on this Mac. Explicit `--start-at` resumes
after verified completed stages; existing training run directories are protected.

Status/log: `data/us-robustness-int5-20260917/pipeline-status.json` / `pipeline.log`.
Runs: `runs/ordered-h128-us-robustness-pilot-20260917` and
`runs/ordered-h128-us-robustness-int5-20260917`.
Monitor every five minutes: process activity, finite losses, actual steps,
validation/checkpoints, memory and disk. Do not modify healthy active training
code/data or duplicate jobs. A process launch is not proof of effective training.

### Pilot decision — 2026-09-17

The 24-epoch pilot finished but failed its predeclared old-US clean guard by
8/2,000 dev examples. That failed result remains unchanged. After reviewing
the frozen epoch-24 evaluation and actual WebGPU results, the user accepted
the small clean-accuracy tradeoff and deprioritized separator diversity.
Proceed with the authorized full run using `--start-at training`, from scratch,
without another pilot, separator changes or more source collection. This is an
explicit pilot-gate waiver, not a passing gate or a change to full-run selection
and release guards. The pilot evaluation already inspected the test panels;
describe subsequent results as held-out diagnostics, not a newly blind test.
Keep the published model untouched and report status every five-minute check.
