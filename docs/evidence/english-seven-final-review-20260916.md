# Seven-country candidate review

17 September release update: original code is MIT; the user approved preserving
upstream model notices. The exact int8 artifact has now passed the external browser
check: [release evidence](release-qualification-20260917.json). The review below
records the earlier nomination and its then-pending publication decision.

## Decision

Nominate **epoch 12, int8 GPA3**, as the seven-country **research candidate**.
It is the winner under the predeclared country-macro validation criterion,
not selected by the external GeoSearch results. Do not claim production readiness,
worldwide support or libpostal equivalence. Publication remains blocked on unresolved
redistribution/licensing decisions; nothing was published in this review.

Training completed 12 full epochs in 13,772.94 seconds. Validation macro exactness
rose from 98.7544% at epoch 8 to 98.9687% at epoch 11 and 99.0044% at epoch 12.
The run stopped at its epoch budget, **not demonstrated convergence**. No further
training is implied by this nomination.

## Actual browser qualification

[Recorded browser evidence](english-seven-browser-20260916.json): both float32 and
int8 passed all 29 fixtures on the local Apple Metal-3 hardware adapter, without a
fallback adapter, in Chromium 152. Components, UTF-16 offsets and reconstructed BIO
paths matched. This is fixture-level parity, not an exhaustive correctness proof
or a Safari/Firefox qualification.

The int8 download is **154,562 bytes** (float32: 617,804). Mixed-fixture warm median
was **1.7 ms** for int8 and 2.0 ms for float32. Setup ran sequentially with shared
cache state: do not use its timings for a cold-start comparison. Int8 storage is
dequantized by the runtime; this does not imply native int8 GPU arithmetic.

Same-source frozen holdout: float32 **12,022/12,115 (99.2324%)**; int8
**12,019/12,115 (99.2076%)**. The net loss is three addresses, all in the US counts.
This supports the smaller artifact but is not representative real-world accuracy.

## Frozen public diagnostics: country tradeoffs

Exact seven-field token-multiset agreement; case, commas and whitespace ignored.
These are previously inspected Senzing diagnostics, not a blind population benchmark.

| Country | Rows | Historical v6 epoch 1 | Seven-head v7 base | This run epoch 8 | Epoch 12 |
|---|---:|---:|---:|---:|---:|
| US | 2,233 | 1,922 | 1,982 | 2,053 | 2,130 (95.39%) |
| UK | 255 | 220 | 222 | 231 | 232 (90.98%) |
| AU | 76 | 24 | 17 | 21 | 33 (43.42%) |
| NZ | 51 | 43 | 22 | 40 | 38 (74.51%) |
| ZA | 53 | 43 | 24 | 23 | 39 (73.58%) |

Epoch 12 improves four of five public-country slices versus epoch 8; NZ loses two
addresses. It beats v7 base on all five, but does not recover historical v6's NZ/ZA
scores. Canada/Ireland have no entries in this frozen comparator input. Canada has
only 115 same-source test examples. Natural in-scope diagnostics remain **48/53**
for both epoch 8 and 12, with very small non-US samples and AI-reviewed labels.
India/Singapore are out of scope, not grounds for a worldwide claim.

## External US sample

Same fixed 1,000 GeoSearch test inputs, seed 20260916; three normalized exact-text
overlaps excluded from the upstream test pool before sampling. Entity/near-duplicate
and competitor overlap remain unknown. Synthetic noise, not natural production traffic.

| Group | Rows | Epoch 8 | Epoch 12 float32 | Senzing v1.2 | Deepparse BPEmb+attention |
|---|---:|---:|---:|---:|---:|
| All | 1,000 | 873 | 879 | 877 | 752 |
| Four fields present | 770 | 710 | 719 | 682 | 741 |
| At least one field absent | 230 | 163 | 160 | 195 | 11 |

The two-address overall lead over Senzing is not evidence of general superiority.
Partial inputs regress by three versus epoch 8 and remain markedly behind Senzing.
These external results are float32; do not present them as measured int8 accuracy.

## Remaining work and evidence

- The requested browser qualification and candidate review are complete.
- Preserve source/runtime/export/checkpoint hashes and local-only evidence before
  eventual publication. Licenses remain undecided; do not assign one implicitly.
- Missing-city coverage is a plausible future bounded data experiment, not a change
  made to this candidate or a requirement silently added to this release review.

Local evidence: `runs/ordered-h128-english-seven-20260916/{completion.json,heldout-test.json,protected-diagnostics/scores.json}`;
`data/geosearch-sample-20260916/{manifest.json,scores12.json,paired12.json}`;
`data/competitor-comparison-20260916/seven-label-scores.json`;
`runs/ordered-h128-seven-v7-base-20260916/frozen-evaluation/scores.json`.
GeoSearch reproduction: run `docs/evidence/geosearch-sample-20260916.py ours12`
then `score12` after the original sample preparation and competitor runs; outputs
refuse overwrite. Browser reproduction: serve the repository on localhost and open
`packages/core/test/browser-parity.html?export=/runs/ordered-h128-english-seven-20260916/export`.
