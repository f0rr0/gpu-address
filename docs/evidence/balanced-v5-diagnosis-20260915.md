# Balanced-v5 diagnosis: fix casing robustness next

The final H128 checkpoint learns its source supervision, but transfers poorly to
different input presentation and natural Indian address conventions. A case-only
counterfactual exposes a large, actionable weakness without changing architecture
or collecting another corpus. No training, runtime, or benchmark labels were changed.

## What was measured

Checkpoint: `runs/ordered-h128-balanced-v5-scratch-20260915/last.pt`, epoch 2,
SHA-256 `5808f68d2284e579bc6804a1e87f795c5cfbe256e4e6f11ea51b72f00a959517`.
Inference uses its saved source, CPU, one thread. Single-row versus batched predictions
were checked. Diagnostic selection seed: 20260915.

| Diagnostic | Exact agreement |
| --- | ---: |
| Uniform training-presentation sample | 1,961/2,048 = 95.8% |
| US training presentations, separate country sample | 274/300 = 91.3% |
| UK training presentations, separate country sample | 269/300 = 89.7% |
| India training presentations, separate country sample | 259/300 = 86.3% |
| Existing protected source-dev, Latin-script supported inputs | 11,911/13,516 = 88.1% |
| Newly reviewed India pilot, not used in training | 31/359 = 8.6% |

These are exact ordered-span agreements. The overall source-dev mix is not identical
to the training mix; its aggregate is not a controlled generalization-gap estimate.
The training sample weights repeated presentations, not unique premises. Country
samples are diagnostic oversamples and are not pooled into the uniform result.
The India pilot is selected, AI-reviewed supervision, not representative human gold.

Compatible source/country slices corroborate that the model learned source patterns:

| Country/source | Sampled training | Protected source-dev |
| --- | ---: | ---: |
| India / worldwide-in | 191/210 | 89/117 |
| UK / Senzing formatted-random | 47/48 | 426/431 |
| US / Senzing GeoPlanet formatted addresses | 50/51 | 82/84 |

These match source family, not necessarily address-type distribution or source
snapshot. They are provisional source-label agreement, not semantic certification.
Protected source-dev was already excluded by the corpus-building protection gates;
this diagnosis did not create a holdout after training.

## High-confidence finding: case sensitivity

On identical public addresses, changing only input case produces:

| Country | Original input | Uppercase input | Title-case input |
| --- | ---: | ---: | ---: |
| US, 2,233 | 175 (7.84%) | 1,803 (80.74%) | 829 (37.12%) |
| UK, 255 | 88 (34.51%) | 143 (56.08%) | 148 (58.04%) |
| India, 54 | 8 (14.81%) | 12 (22.22%) | 10 (18.52%) |

Metric: case-normalized field-content agreement, not ordered-span exact. This is a
counterfactual diagnosis, **not** an 80.7% accuracy claim on unchanged US inputs.
Uppercase rescues 1,673 US failures but breaks 45 formerly correct examples. It also
breaks 23 UK and one India example. Do not ship unconditional uppercasing.

The reverse intervention supports the same finding: on ASCII-only protected source-dev
rows, lowercasing reduces US agreement from 202/294 to 70/294, UK from 581/672 to
225/672, and India from 95/125 to 50/125. ASCII restriction preserves exact offsets.

Example, original: `135 meadowbrook drive, manchester ct 06042`.
The model labels `manchester ct 06042` as `level`. Uppercasing the same address yields
the correct separate city, state, and postcode. Other failures remain after uppercasing.

The sampled training rows contain zero entirely lowercase US addresses (354 sampled
presentations) and zero UK addresses (365); the public sets contain 2,177/2,233 and
223/255 lowercase inputs respectively. These sample counts describe observed input
case, not the full corpus. The byte encoder is case-sensitive. The current training
loop reads the fixed corpus unchanged, with no online case augmentation. An older
`prepare.variant()` helper exists, but is not invoked by this training path and also
changes layout/omits fields; using it unchanged would confound a case-only experiment.

## Review of 100 current-model failures

Deterministic hash ranking within US (34), UK (33), India (33); selected from final
checkpoint failures. Two Sol-medium reviewers individually inspected disjoint halves.
Root checked findings and corrected an unrelated-place mention and an overconfident
claim about an ambiguous bare number. These are AI diagnostic judgments, not new gold
or a population estimate; no benchmark references were changed.

| Classification | Count |
| --- | ---: |
| Clear model error | 52 |
| Both model error and reference ambiguity/policy mismatch | 44 |
| Ambiguous reference, no established independent model error | 2 |
| Reference/policy mismatch only | 2 |
| Tokenizer representation limit established | 0 |

The main US/UK pattern is city/state/postcode tails misclassified as unit or level,
plus road directionals and locality boundaries. Reference defects do not explain
away most observed errors. No representation issue was found in the sampled training
rows or evaluated Latin source-dev labels. Public references lack exact offsets,
so their representation assessment is individual inspection, not an exhaustive
machine-checked upper bound. Previously found fused-token Indian inputs remain a
separate known limitation; they do not explain these 100 failures.

India has an additional supervision/domain gap: 29 of its 33 reviewed failures are
mixed, two clear model errors, one ambiguous reference and one reference-only mismatch.
References sometimes absorb buildings, landmarks or neighborhoods into road/number;
the model independently confuses premises, roads, city/state/country and relations.
Its 31/359 exact matches on the separate AI-reviewed pilot show the problem persists
with our own annotation policy (schools 21/181, company addresses 9/171, banks 1/7).
Do not treat casing repair as sufficient for India or claim benchmark disagreement
is all annotation noise.

## One next experiment

Train the same H128 from scratch on the same balanced-v5 exposure, changing only
training-time casing variation (retain original forms and expose lower/upper/title
variants). Preserve original source files, labels and output-span semantics; handle
Unicode case-length changes explicitly rather than corrupting offsets. Keep the
same seed, optimizer and update budget; save both epochs and compare matched epochs.

Evaluate on unchanged public/natural inputs and protected source-dev, with the same
case stress tests as diagnostics. Success means improved original-input US/UK results
and smaller casing sensitivity without a material regression on original source/natural
inputs; report India separately. Do not choose a checkpoint from the eight-row dev set.

Do not simultaneously add the 359 rows, change country weights, tokenizer, architecture,
or introduce a teacher. Keep the 359 as a diagnostic for this comparison, not a permanent
test set if later admitted to training. If the casing experiment succeeds, the remaining
India gap calls for broader policy-consistent natural supervision, not more copies of
coarse source labels. This experiment is recommended, **not launched**.

## Reproducible evidence

- [Diagnostic script](diagnose-balanced-v5-20260915.py)
- [Metrics and input hashes](../../data/diagnosis-balanced-v5-20260915/summary.json)
- [Case probe, paired predictions and India pilot metrics](../../data/diagnosis-balanced-v5-20260915/case-probe.json)
- [Original 100 failures with predictions](../../data/diagnosis-balanced-v5-20260915/public-failures-100.json)
- [Review A](v5-failure-review-a-20260915.json), [review B](v5-failure-review-b-20260915.json)

Initial source-dev exploration used an incomplete script filter. That preliminary
output is retained separately under `data/diagnosis-balanced-v5-20260915-initial` and
is not used here. Final source-dev uses the repository's Latin/Common/Inherited rule.
No additional packages, training runs or runtime changes were introduced.
