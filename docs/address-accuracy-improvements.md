# Improving address accuracy without growing the model

This follows the [first training campaign](address-training-results.md). The aim is still to parse address fields locally in the browser, preserving the user's text. It is not geocoding, deliverability validation, or guessing missing fields.

Follow-up: [the additional-source campaign](address-source-quality-audit.md) executes the data-expansion hypothesis and reaches 77.79% public agreement, with material country-level regressions recorded alongside gains.

## What the failures suggest

The previous best model gets **74.35%** of the 12,868 public benchmark addresses completely right under normalized field-map comparison. Its generated development score is **84.22%**, using the stricter ordered raw-span metric. These are different populations and metrics, not contradictory measurements.

A fixed sample of 3,000 addresses actually used in training scores **85.63%** on ordered raw spans. That small train/development gap suggests we have not exhausted the existing model's ability to learn. It does not prove that more training will fix everything: noisy labels and ambiguous inputs also limit training accuracy.

The failures point to four separate issues:

1. **Training may have stopped too soon.** Three passes at one learning rate need not be enough. First try additional passes with a smaller learning rate, keeping the model and sampled data fixed.
2. **We throw away potentially useful evidence.** Tokenization makes `12 Main Street` and `12\nMain Street` identical inputs. A line break can separate address components. Preserve a compact whitespace/newline cue and measure whether it helps beyond the extra training alone.
3. **Geographic and field coverage is uneven.** In the public suite, the previous model gets only 1/177 Taiwan examples completely right. Counting countries in the training manifest does not establish usable coverage. Country, city, suburb, and administrative-area confusions need targeted data work, not just more random variants.
4. **The reference labels also need scrutiny.** There are 1,875 public cases where libpostal matches the reference and our model does not, 660 in the opposite direction, and 1,426 where neither matches. Copying every libpostal answer would erase some correct student answers while reproducing teacher errors. Disagreement is a review queue, not automatic ground truth.

The constrained sequence decoder is already valuable: independent per-token argmax gets only 2,695 public cases right, versus 9,567 with the CRF. The network was trained jointly with that decoder, so this is not a fair comparison against a separately trained argmax model; it does show that simply deleting the decoder breaks this checkpoint.

The active training corpus contains 94,369 rows marked `existing-tagged`, before counting controlled augmentations. Selected original counts illustrate the coverage issue:

| Country | Original training rows |
| --- | ---: |
| United States | 16,739 |
| Japan | 12,800 |
| China | 12,142 |
| Taiwan | 43 |
| India | 49 |
| Egypt | 8 |
| Liechtenstein | 4 |

Some target fields are similarly sparse: only nine `entrance` occurrences and seven `world_region` occurrences in these originals. The data audit found no conflicting field assignments for identical token sequences in the selected 100,000 rows; this limited check does not establish that the labels are correct. There are 6,519 selected training rows containing line breaks, so the proposed boundary cue has some learning material but is not broadly represented.

## Controlled experiments

Both branches start from the same `independent-layout-100k/best.pt`, use the same seeded 100,000 training rows and fixed 6,000 development rows, and run three additional epochs at learning rate **0.0005**. AdamW is freshly initialized; this is a warm start from weights, not exact optimizer-state resumption. The best checkpoint in each branch is selected only by generated development exact-span accuracy.

| Branch | Change | What it tests |
| --- | --- | --- |
| `continuation-100k` | Additional training at a smaller learning rate | Whether the existing representation/model can improve without growing |
| `gaps-100k` | Same training plus a preceding-whitespace/newline byte | Whether boundary evidence adds value beyond additional training |

The gap cue reuses the existing byte vocabulary. Both models have **615,244 parameters**. The cue preserves whitespace presence and distinguishes line breaks; it does not preserve the exact number of spaces. Raw input spans remain unchanged. The extra cue may increase padded byte width and work slightly; parameter count alone is not a latency measurement.

This comparison isolates the gap cue from the additional training. It does **not** independently separate the effect of more epochs from the lower learning rate, or establish robustness across random seeds.

## Results: retain the simpler continuation

Executed September 14, 2026, on Linux CPU with four PyTorch threads per run. The two independent training runs ran concurrently. No paid compute was used and no Mac/browser timing is claimed.

| Checkpoint | Generated dev exact spans, 6,000 rows | Public field-map agreement, 12,868 rows | Training-sample exact spans, 3,000 rows |
| --- | ---: | ---: | ---: |
| Previous baseline | 84.22% | 74.35% (9,567) | 85.63% |
| **Continuation, best at additional epoch 2** | **87.37%** | **75.71% (9,743)** | **92.43%** |
| Gap cue, best at additional epoch 3 | 86.90% | 72.25% (9,297) | 92.70% |
| Native libpostal, previously measured | — | 83.79% (10,782) | — |

The retained continuation improves public agreement by **1.37 percentage points**, a **5.33% relative reduction in benchmark errors**. It is still 8.07 points behind the measured native baseline. All three scheduled epochs were executed: the continuation's third epoch fell to 86.83% on generated development, so the selection rule correctly retained epoch 2. Training loops took 401.9 and 404.4 seconds, excluding loading/export; the chosen continuation checkpoint incorporates the original three epochs plus two additional epochs.

Paired public results matter more than the headline alone:

| Branch versus previous baseline | Previously wrong → correct | Previously correct → wrong | Net additional correct |
| --- | ---: | ---: | ---: |
| Continuation | 649 | 473 | +176 |
| Gap cue | 595 | 865 | −270 |

Continuation gains include Germany (+95 correct), Canada (+44), Denmark (+35), and the US (+34). It regresses in Austria (−39), South Africa (−16), Slovakia (−16), and other countries. This is a better aggregate research baseline, **not** a uniformly better parser for every locale.

Country omission also worsens from 860 to 966 public cases in the continuation, despite its overall gain. The gap variant misses country fields in 1,384 cases. Extra boundary cues did not solve the intended problem in this experiment; we leave `--gap-features` off. This rejects this encoding/warm-start recipe, not the general possibility that formatting information can help. Fine-tuning from a model that previously never saw the cue and the mismatch between generated layouts and public inputs are plausible explanations, not established causes.

The train/development gap widens from roughly 1.4 to 5.1 percentage points for the retained model. More training helped, but it helped memorizing/fitting the training population much more. That changes the next priority: broaden and audit the training distribution before simply adding more passes or parameters.

### Size and execution checks

The retained model still has **615,244 parameters**. Its stored-int8 NPZ is **612,844 bytes (598.48 KiB)**; the float ONNX is 2,463,168 bytes, or 2,255,260 with Brotli. The runtime and decoder are additional assets, so this does not establish a sub-megabyte browser package.

Stored-int8/dequantized inference ties float at 87.37% on the 6,000 development cases, but changes 21 outputs: six newly wrong and six newly correct, plus changes among already-wrong outputs. Equal aggregate accuracy is not identical behavior. The reported public score uses float weights; public int8 accuracy was not measured in this campaign.

Both branches pass 29 Python/ONNX/Wasm fixtures, including CJK, emoji/UTF-16 offsets, line breaks, tabs, and a 64-byte token. For the retained model, maximum emission differences are 0.00001144 for ONNX CPU and 0.00000954 for Wasm; decoded paths and raw spans agree. Wasm was run through ONNX Runtime Web under Node, not Safari or Chromium. The existing full data/span/split and CRF checks also pass.

Only one seed and one continuation learning rate were tested. The public suite has influenced our investigation; these numbers are development evidence, not a final accuracy guarantee.

## The next data improvements, in priority order

### 1. Buy information, not repeated examples

Add **new original addresses** for weak countries, scripts, and fields. Draw from broader source partitions rather than repeatedly augmenting the same bounded archive prefix. Track unique streets/entities as well as row counts. Split originals before rendering variants; keep every variant with its original's partition.

For training, test a mix of ordinary frequency sampling and a capped country/field-balanced component. Pure balancing can overfit the few available rare examples, so do not give a country with ten originals the same effective diversity as one with ten thousand. Compare both overall accuracy and per-country/per-field results on unchanged evaluation data.

### 2. Make messy data resemble what people paste

The previous campaign already showed that a convenient generator can teach the wrong shortcut. Independently vary casing, separators, and optional fields; now audit how often those transformations occur in real inputs. Add whitespace and punctuation noise, missing administrative fields, unit/floor forms, abbreviations, and embedded surrounding text only where a known label-preserving transformation can produce defensible spans.

Do not scramble geographic hierarchy or replace city names independently of their states and then call the result a real address. Do not apply Latin-oriented typo rules uniformly to every script. Keep clean, noisy, partial, and embedded inputs as separate evaluation slices so one easy group cannot conceal another's failures.

### 3. Resolve label ambiguity before optimizing it away

Audit examples where labels alternate between city, suburb, city district, and state district. Define what each field means consistently with the intended API and record genuinely ambiguous cases. A string alone cannot always reveal the correct administrative level. Returning extracted text is feasible; reconstructing facts absent from that text requires additional information.

Use the existing blind real-input annotation queue to establish independent labels. Review errors by country and failure type, not only the first fifty examples. Keep a fresh final set untouched by model/generator decisions; the repeatedly inspected public suite is now a development benchmark.

### 4. Use the teacher selectively

Only after auditing a sample of the real web strings, test teacher-labeled data as a separately tracked training addition with capped weight. Preserve original inputs, teacher version, alignment failures, and provenance. Compare against human-reviewed cases, including cases where the teacher was wrong. Agreement with libpostal alone is not the objective.

### 5. Separate parsing accuracy from safe acceptance

The current model assigns fields even to non-addresses. A future rejection/abstention mechanism must be trained and calibrated on real negatives, partial addresses, and ambiguous cases. Report **accuracy at a stated coverage**, alongside ordinary all-input accuracy and false acceptance. Hiding difficult addresses behind rejection cannot count as a universal accuracy gain.

## When to change the architecture

Only after the controlled continuation and coverage work, compare a modestly wider model at the same data budget. If training accuracy improves substantially but held-out accuracy does not, more capacity is not the immediate answer. If both improve, evaluate the added compressed bytes and real browser latency before choosing it.

A country hint could resolve some ambiguity when the application already knows it, but it changes the input contract. Any future hinted model must also be evaluated without hints and with incorrect hints. Do not feed benchmark country metadata to a model advertised as string-only parsing.

Compression comes after choosing the accurate candidate. Recheck quantization-induced output changes and Python → ONNX → Wasm parity. Compressed weight size is not the total browser download, and Node Wasm parity is not a Mac browser performance result.

## Reproduction and evidence

See the [experiment README](../README.md) for runnable commands. Local diagnostics are in `runs/independent-layout-100k/diagnosis.json`, paired predictions in each run's `diagnostic-predictions.jsonl.gz`, and epoch results/checkpoint provenance in each run directory. Raw data and model artifacts are retained locally and ignored by Git.

From `experiments/address-parser`, reproduce the retained branch with:

```sh
.venv/bin/python train.py --data data/layout-independent --limit 100000 --dev-limit 6000 --epochs 3 --lr 0.0005 --init runs/independent-layout-100k/best.pt --run runs/continuation-reproduction
.venv/bin/python diagnose.py --run runs/continuation-reproduction --compare runs/independent-layout-100k
.venv/bin/python export.py --run runs/continuation-reproduction --data data/layout-independent
```

For the rejected boundary-cue branch, use a separate run directory and append `--gap-features` to the training command, keeping the same original parent checkpoint. Do not initialize it from the continuation branch: that would change the comparison.
