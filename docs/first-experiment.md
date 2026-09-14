# First experiment: a tiny measurement parser

This remains an optional learning experiment. The current product shortlist is in [Frontend opportunities](webdev-opportunities.md); no measurement-parser implementation has been started.

## The question

Can a compact learned tagger improve recognition of everyday measurements over a small deterministic parser, while preserving an attractive browser footprint?

This is an experiment specification, not an implementation plan already in progress. All sample counts, budgets, and success thresholds below are proposed decisions. None is a measured result.

## Version-one contract

Input is a short English phrase with an explicit locale. Output is a list of measurement spans, each containing its source offsets, exact numeric value or range, unit, and comparison relation. The result can also say that an interpretation is ambiguous or unsupported.

Start with decimal-dot English, mass/length/volume, and a short explicit unit list: g, kg, lb, oz, mm, cm, m, in, ml, and l, plus their spelled-out forms. Treat ounces as ambiguous unless context or a caller-provided dimension hint resolves them. Locale-specific unit definitions must be explicit. Currency, temperatures, compound rates, pack-size relationships, and three-dimensional sizes are separate later slices.

Illustrative expected behavior:

| Input | Expected interpretation |
| --- | --- |
| `2.5 kg` | Scalar mass, 2.5 kilograms |
| `between 2 and 3 kg` | Range, 2–3 kilograms |
| `under half a litre` | Volume less than 0.5 litres |
| `a five-pound bag` | Scalar mass, 5 pounds |
| `I spent five pounds` | Unsupported currency meaning; no mass output |
| `Model 500 XL` | No measurement |
| `12 oz` | Ambiguous mass/volume without a relevant hint |
| `1,5 l` | Unsupported numeric locale in this first contract |

Spans retain the original text. Numeric parsing, fraction arithmetic, range construction, unit definitions, and conversions stay in ordinary code. Tests must distinguish an exact decimal/fraction representation from a floating-point display value.

## Establish the baseline first

Write down the label policy before collecting examples. Build a compact grammar/lexicon baseline for the same contract and compare relevant outputs from Quantulum3 and Microsoft Recognizers-Text. These are existing systems with different scopes; normalize their results and mark unsupported cases rather than counting every output mismatch as an error.[^1][^2]

Collect a diagnostic development set spanning scalar quantities, fractions, ranges, comparisons, punctuation, ambiguous words, and negatives. Manually label a separate real-text test set before tuning. A practical initial target is 200 development examples and 400 held-out examples across these slices. This is enough to find common failures, not to establish rare-error reliability.

## Make training pairs

Generate known quantity structures and render multiple surface forms. Keep the structure and source spans as labels. Start with 10,000–30,000 generated phrases, then inspect failures before increasing volume.

Separate semantic records and renderer/template families before generation. Keep near duplicates together. Add reviewed real phrases from source groups absent from the test set. Include negative examples that resemble measurements; decide their training proportion using development results rather than assuming one universal ratio.

Store source and label provenance alongside each row: generator/version, original source where applicable, teacher output, and any human correction. Teacher agreement can supply cheap labels, but independent test labels must follow the written contract.

## Train the smallest adequate predictor

Compare a linear or CRF baseline with a small neural tagger. The neural candidate can use hashed spelling/shape features, a 16–32-dimensional embedding, and local context plus a small bidirectional recurrent or scan layer. Copy recognized words from the source instead of predicting their spelling.

Treat 50,000–250,000 parameters as an initial exploration range. Start training on CPU or PyTorch MPS with modest batches. Measure a representative short run on the M1 Pro before estimating a full run. No NVIDIA GPU purchase is justified by this experiment specification.

## Decide whether it is worth continuing

Use these provisional gates:

- At least 20% fewer exact-structure errors than the compact grammar on the agreed in-scope test slice, with error counts reported alongside percentages.
- At least 98% precision on accepted measurement interpretations and at least 80% coverage of unambiguous in-scope inputs. Report ambiguity and unsupported cases separately.
- No material increase in measurement detections on negative examples; report the count rather than hiding it in aggregate accuracy.
- A plausible complete compressed package budget below 250 KB. Count runtime, features, unit data, and weights together. This is a stretch target, not an inferred consequence of parameter count.

With only hundreds of examples, uncertainty intervals and slice counts matter. Any tuning after opening the test set makes it development data; obtain a new independent set before claiming generalization.

Continue if the model improves real cases, or if it matches a larger existing system closely enough to offer a demonstrated deployment advantage. Stop or retain the deterministic baseline if the difference is marginal.

## Browser experiment after the quality gate

Export float weights first and compare browser CPU outputs with Python on fixed fixtures. Quantize and repeat the same evaluation. Benchmark cold start and warm single-phrase/batched latency, plus peak memory and complete compressed transfer size.

Only then consider WebGPU. Measure preprocessing, dispatch, inference, readback, and decoding together. A one-phrase API may remain faster and simpler on CPU even when its network operations parallelize well.

The first demo should show the input, highlighted spans, structured interpretation, and uncertainty. It should make wrong answers easy to inspect. That supplies a useful foundation for a training case study regardless of whether GPU inference ultimately wins.

## Sources

[^1]: Quantulum3 contributors. [Quantity parsing, disambiguation, and classifier training](https://github.com/nielstron/quantulum3).
[^2]: Microsoft. [Recognizers-Text](https://github.com/microsoft/Recognizers-Text).

See [build notes](build-notes.md) for the source-backed architecture and hardware precedents behind the proposed experiment.
