# How tiny learned libraries are built

## The shared design

gpu-lexer and gpu-time each put roughly forty thousand learned parameters behind a narrow software interface. Their model predicts categories; conventional code turns those predictions into useful output. Both have PyTorch training paths supporting Apple MPS.[^1][^2][^3][^4]

```text
Offline construction
examples + trusted labels → train weights → evaluate → quantize → export

Browser operation
input → compact features → learned scores → labels/spans → ordinary code → result
```

This separates two kinds of work. The developer designs the features, network, output contract, and evaluation. Training adjusts numerical weights to reduce errors on labeled examples. Browser deployment only needs the forward calculation, exported weights, and surrounding application logic.

## gpu-lexer: learn the highlighter's labels

### Data and supervision

The project gathers source files and runs Shiki offline. Shiki's TextMate scopes are mapped to nine visual labels: plain, comment, string, number, keyword, type, function, constant, and operator. Additional lexical states provide auxiliary supervision. This produces many labeled examples without manual token annotation.[^5]

Repositories/packages are separated between training and verification. The model card records about 4.68 million prepared training parts per natural corpus pass. Its reported held-out agreement with the normalized teacher is 88.02%, with 79.09% styled macro F1. These measure an approximation of a highlighting convention, not programming-language correctness.[^1]

### Model and runtime

A mechanical CPU pass splits source into words, whitespace, newlines, and symbols. It packs hashes, length, shape, edge-character, and neighboring-symbol features. Small learned vectors combine those features. Local mixing, bidirectional scans, and a hierarchical tree supply context before a nine-way classifier predicts each part's label. JavaScript reconstructs and merges source spans.[^6]

The current model has 41,609 training parameters and 41,321 deployed six-bit weights. Its complete minified JavaScript, shader, and weights occupy 27.46 KiB with Brotli. Quantization-aware training helps the model tolerate low-precision storage; the browser still uses floating-point intermediate calculations.[^1][^6]

The pipeline includes difficult-example replay, language weighting, calibration, and regression guards. The tracked active artifacts support continuation, while historical optimizer states and every experimental run are not included.[^7]

### What to borrow

An existing library can be a scalable teacher. Choose a compact target, such as a visual category, before choosing a network. Keep source offsets through every stage so a prediction maps directly back to the input. Measure disagreements with the teacher separately from independently established correctness.

The WebGPU implementation is substantial deployment engineering. A small network does not automatically make GPU dispatch worthwhile on short input.[^6]

## gpu-time: learn recognition, retain calendar logic

### Data and supervision

The synthetic generator constructs schedules and renders language with known labels. Real English supplies additional examples through a harvesting and agreement pipeline. The model card also records 1,004 authored teacher examples with language-model-proposed labels accepted through compiler checks.[^2][^8]

These sources have different weaknesses. Synthetic language can be repetitive. Parser agreement preferentially includes easy cases shared by the parsers. Compiler acceptance verifies structural or semantic constraints but cannot by itself establish that the labels match what a person intended.

### Model and runtime

Compact token features feed local context mixing and two scan layers. The network predicts token roles and expression boundaries. A CRF transition matrix and Viterbi decoding choose a coherent label sequence. A TypeScript compiler constructs a schedule; a resolver applies reference dates, timezones, and calendar rules.[^9]

The model has 38,745 parameters, 40 role slots including reserved slots, and six-bit weights. The complete package is 44,682 bytes with Brotli. Some of the model's capacity is devoted to sequence relationships: its 40 × 40 transition matrix alone contains 1,600 parameters.[^2]

Illustrative decomposition:

```text
"every Tuesday at 3 pm"
   → recurrence / weekday / hour / meridiem roles
   → structured weekly schedule
   → concrete occurrences calculated by ordinary code
```

This is a conceptual illustration, not an exact serialization of the project's training labels.

### The failure worth remembering

An earlier model failed to recognize the hour in “Dinner at 8 at Nobu.” Training examples overwhelmingly associated the relevant context with a daypart. The correct interpretation was often ranked second, but the sequence score favored the wrong path. Rebalancing alone traded this failure for other regressions; targeted sequence-level training addressed the competition between interpretations.[^2]

A separate update learned a new expression family but broke eleven previously correct examples. The project documents focal distillation, which encourages preservation of a reference model's correct behavior during updates.[^9]

**Lesson:** inspect distributions and complete decoded outputs. More examples can reinforce the wrong association, and better average token accuracy can hide worse application behavior.

## What an M1 Pro with 16 GB can reasonably do

Training small taggers and classifiers in this family is a realistic local experiment. The checked training implementations explicitly support MPS.[^3][^4] This is a feasibility assessment, not a measured time estimate or proof that every default batch configuration fits.

At 40,000 parameters, float32 weights occupy approximately 160 KB. Training also needs gradients, optimizer states, activations, batches, and framework memory. Sequence length and batch size can dominate memory; multiplying weight size by a constant does not estimate total memory reliably.

Start with modest batches, stream data, and measure a short representative run. Reduce batch size or sequence length before buying hardware. A bigger machine becomes useful for repeated experiments, large corpora, or architectures whose measured memory/throughput exceed the laptop's limits.

Exact checkpoint reproduction is a separate matter. gpu-time's documented continuation history depends on earlier checkpoints that were not all present in the public tree when checked. Public inference artifacts and training code do not guarantee bit-for-bit reproduction of the released model. See the [full reproducibility discussion](research.md).

## Comparable case studies

| Project | Useful evidence | Lesson |
| --- | --- | --- |
| RNNoise | Author explains features, synthetic noisy/clean pairs, network, and C export | Learn the difficult part inside an established algorithm |
| Magika | Paper covers dataset, architecture, evaluation, and hardware | A small model can require a large production data effort |
| CLD3 | Published hashed character-ngram architecture and browser binding | Compact features work well for narrow text classification |
| Tiny timer model | Author documents output-language changes and failure-driven training | Choose an output representation that keeps exact operations in code |
| NYT ingredient tagger | Human-labeled ingredient data and CRF training code | Sequence tagging has a practical history beyond recent neural libraries |
| Web2Text | DOM-derived features, neural scores, and structured decoding | Browser document cleanup is another narrow labeling problem |

RNNoise's original illustrated account describes 42 input features, 22 band gains, generated mixtures of speech and noise, and an 85 KB quantized model. It is the clearest conceptual starting point.[^10]

The Magika paper reports 30 epochs taking 6 days and 21 hours on a single RTX 4090, with a Ryzen 7950X and 126 GB RAM. That is the paper's experiment, not a minimum hardware requirement for all content-type classifiers.[^11]

CLD3 has a character-ngram/embedding classifier and a separate WebAssembly JavaScript binding.[^12] The timer article fine-tunes T5 rather than training a forty-thousand-parameter tagger, but its compact intermediate language is relevant.[^13] The NYT and Web2Text projects add useful precedents for the [project ideas](project-ideas.md).[^14][^15]

## Practical principles

1. **Define the output contract first.** A dozen labels and copied source spans are easier to learn and validate than arbitrary generated JSON.
2. **Specify the source of correct answers.** Existing software, semantic generation, human annotation, or a larger model each produces different supervision.
3. **Include examples where nothing should happen.** Numbers in model names, prose that resembles a date, and code inside strings are essential negatives.
4. **Separate data by its source.** Hold out repositories, websites, recipes, conversations, or template families as appropriate.
5. **Evaluate the final operation.** Exact fields, correct grouping, preserved content, and false positives matter alongside token scores.
6. **Keep uncertain cases visible.** A calibrated abstention or candidate list can be more useful than an unsupported confident answer.
7. **Compress after establishing usefulness.** Recheck accuracy and browser parity after quantization.
8. **Treat a teacher as a baseline.** A student imitating one teacher has no established accuracy advantage over it. A smaller portable runtime can still be valuable.

## Sources

Source versions were inspected on September 14, 2026. The full research report retains additional pinned references.

[^1]: Vercel Labs. [gpu-lexer model card](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/MODEL_CARD.md).
[^2]: Arik Chakma. [gpu-time model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md).
[^3]: Vercel Labs. [Training device selection](https://github.com/vercel-labs/gpu-lexer/blob/main/packages/training/src/torch-runner.js).
[^4]: Arik Chakma. [gpu-time trainer](https://github.com/arikchakma/gpu-time/blob/main/packages/training/torch/train.py).
[^5]: Vercel Labs. [Shiki label generation](https://github.com/vercel-labs/gpu-lexer/blob/main/packages/training/src/label.js).
[^6]: Vercel Labs. [gpu-lexer architecture](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/architecture.md).
[^7]: Vercel Labs. [Weighted training](https://github.com/vercel-labs/gpu-lexer/blob/main/packages/training/WEIGHTED-TRAINING.md).
[^8]: Arik Chakma. [Schedule generator](https://github.com/arikchakma/gpu-time/blob/main/packages/training/torch/generate.py) and [harvesting pipeline](https://github.com/arikchakma/gpu-time/blob/main/packages/training/torch/harvest.py).
[^9]: Arik Chakma. [gpu-time architecture](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md).
[^10]: Jean-Marc Valin. [RNNoise: Learning Noise Suppression](https://jmvalin.ca/demo/rnnoise/), 2017. [Current repository](https://github.com/xiph/rnnoise).
[^11]: Fratantonio et al. [Magika: AI-Powered Content-Type Detection](https://arxiv.org/html/2409.13768v1), 2024.
[^12]: Google. [CLD3](https://github.com/google/cld3). Kwon. [cld3-asm](https://github.com/kwonoj/cld3-asm).
[^13]: Maksim Ivanov. [Training a Tiny Model to Set Timers from Natural Language](https://maksimivanov.com/posts/training-a-tiny-model-to-set-timers/), May 17, 2026.
[^14]: The New York Times. [Ingredient phrase tagger](https://github.com/nytimes/ingredient-phrase-tagger).
[^15]: Vogels et al. [Web2Text: Deep Structured Boilerplate Removal](https://arxiv.org/abs/1801.02607), 2018. [Code](https://github.com/dalab/web2text).
