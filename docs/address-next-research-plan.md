# Next experiments for the browser address parser

The priority is to establish how accurately this task can be learned with substantially more model capacity and trustworthy supervision. The earlier proposed 1 MiB address-package target is retired. Browser download size, startup, latency and memory remain measurements, but there is no fixed package-size ceiling during accuracy research. The existing small model remains a comparison baseline.

The recommended order is: **establish larger-model accuracy references → improve supervision, exposure and sequence decisions → measure accurate candidates in the browser → compress where the measured benefit warrants it**. Label-policy repair and independent evaluation run alongside the capacity experiments. A script-neutral representation is a specific architecture experiment, especially for native-script inputs. A larger accurate model may itself become the browser candidate; a smaller distilled student is optional.

## Current evidence

The latest model has 615,244 parameters. On the 12,868-example public development benchmark, expanding the data mixture raised exact field-map accuracy from 75.71% to 77.79%. It corrected 755 cases and broke 488 previously correct cases. Germany fell from 1,818 to 1,713 correct out of 2,020, while Singapore rose from 4 to 41 out of 50. The original generated development score fell from 87.37% to 85.90%.[^1]

These are meaningful improvements with meaningful regressions. The 87.53% result on the supplementary source holdout measures agreement with those imported/generated labels. It is not evidence of comparable accuracy on independently annotated natural input. The public benchmark has already influenced development and must remain a development benchmark.[^1]

Two additional diagnostics substantially sharpen the next research decisions.

### The correct parse often ranks below another interpretation

An exact top-eight Viterbi diagnostic was run against the current checkpoint. It asks whether any of the eight highest-scoring label sequences produces the benchmark's expected field map. The dynamic program was checked against exhaustive enumeration on a small random problem; its first-ranked path also matched the existing decoder on every initially incorrect public example.[^2]

| Diagnostic | Exact expected field map available | Fraction of 12,868 examples |
| --- | ---: | ---: |
| Model's actual first choice | 10,010 | 77.79% |
| Among first two label paths | 10,884 | 84.58% |
| Among first four label paths | 11,483 | 89.24% |
| Among first eight label paths | 11,829 | 91.93% |

For **1,819 of the 2,858 current errors—63.65%—an expected answer already occurs among those eight paths**. This supports investigating sequence ranking before assuming all errors require additional model capacity. It does not prove that a small reranker can identify the right answer. The diagnostic uses the expected answer to choose, multiple paths can collapse to one field map, and public field-map equality is looser than exact ordered source-span equality.

The country breakdown separates promising ranking work from deeper problems:

| Country | Actual first choice | Best available among eight | Research implication |
| --- | ---: | ---: | --- |
| Germany | 1,713/2,020 | 1,986/2,020 | Strong motivation for better sequence decisions and regression control |
| Taiwan | 34/177 | 121/177 | Ranking explains many failures; substantial errors remain |
| Australia | 19/76 | 68/76 | Investigate administrative-field decisions and complete-parse ranking |
| Singapore | 41/50 | 45/50 | Preserve the new gain |
| India | 15/54 | 19/54 | Current candidate interpretations remain inadequate |
| South Korea | 2/52 | 8/52 | Data, representation and label conventions need investigation |
| Egypt | 0/50 | 0/50 | Reordering eight existing candidates cannot repair these examples |

The country counts are small in several cases, and examples may share address families. These results identify experiments; they do not establish national accuracy.

### Most of the available pool was never used in the latest run

The trainer sampled **100,000 fixed rows from 496,978**, then revisited that same subset for three epochs. Reconstructing the exact sample using the recorded seed and verified data hash gives:[^3]

| Actual exposure | Rows |
| --- | ---: |
| Rows from the original training pool | 40,584 |
| Rows from the newly added pool | 59,416 |
| Controlled augmentations, across both pools | 51,836 |
| Egypt, all selected rows | 578 |
| Egypt rows containing both house number and road | 167 |
| India, all selected rows | 539 |
| India rows containing both house number and road | 111 |

Thus the data expansion changed the distribution while substantially reducing rehearsal of the old pool under a fixed training budget. This is a plausible contributor to forgetting, not a demonstrated sole cause. Three epochs do not mean three independent 100,000-example samples.

The sampled subset contains 85,349 recorded groups. Group identifiers help control repeated variants, but they do not certify that every group represents a different physical address. More generated strings and more geographical knowledge are different quantities.

## 1. Improve complete-parse decisions without increasing the download

A controlled training intervention should accompany the capacity experiments. Within this comparison, keep architecture and decoder fixed. Add a loss that penalizes an incorrect winning sequence when it outranks the correct sequence. Testing this hypothesis does not require delaying the larger references.

The present CRF already trains a distribution over complete label sequences. This proposal therefore strengthens the connection between training and the final decision; it does not introduce sequence modeling for the first time. The additional term explicitly compares the decoded wrong answer with the gold answer:

```text
ordinary CRF loss
+ small weight × penalty when an incorrect winning path outranks the gold path
```

GPU Time provides a particularly relevant case study. Its architecture describes this additional sequence penalty, mixed with the ordinary loss. It also reports that making the penalty too strong improved a targeted set while damaging other cases. Its coefficients are specific to its loss scales and should not be copied into this experiment.[^4] Classical structured-prediction research also investigates objectives that more directly reflect sequence-level evaluation, although translation and summarization results do not establish address-parsing gains.[^5]

**Experiment:** use trusted training spans to form the gold path; compute the winning path with detached decoding; backpropagate through both path scores. Apply no extra penalty to a sequence already decoded correctly. Test a small coefficient range after measuring the relative gradient scales. Keep CRF likelihood as the primary loss.

Initially exclude weak or ambiguous rows from this extra penalty. Forcing a noisy complete annotation to win more strongly would amplify its errors. Where several outputs are genuinely acceptable, the training target should allow those interpretations instead of inventing a single arbitrary winner.

**Decision:** retain the change only if complete-output accuracy improves without unacceptable country regressions. Track both first-choice accuracy and top-eight availability. An improvement in ranking with stable candidate availability is different from learning additional interpretations.

A separate inference-time reranker is a later option. It could examine a few candidate parses with whole-address features. It would add browser computation and another model to maintain, and would require training candidates generated out of fold. The training-only intervention has a simpler deployment path and should be tested first.

## 2. Stop new learning from unnecessarily breaking old successes

The latest run's 488 negative flips are a direct reason to test preservation during training. GPU Time reports using focal distillation to discourage changes where a reference already predicts correctly. The original Positive-Congruent Training paper studies precisely these correct-to-incorrect updates; its experiments concern image classification, so transfer to our CRF requires evaluation.[^4][^6]

Use the stronger earlier checkpoint as a frozen reference **on training examples only**. Give extra preservation weight to rows or tokens where that reference agrees with a trusted label. Leave incorrect reference predictions free to change. Start with emission matching because both models have identical tokenization and label order; test a structured version only if needed.

Do not preserve an old error simply because it was confident. Likewise, teacher agreement cannot resolve a disputed city/suburb convention. Reviewed labels and the declared annotation policy outrank an old model.

Test preservation and sequence ranking separately before combining them. Their effects may conflict: excessive preservation can prevent the intended correction. GPU Time's inspected architecture records an overly strong configuration that essentially reproduced its reference without learning the new behavior.[^4]

Rehearsal should also be explicit. Draw from source/country groups rather than letting the number of imported variants determine exposure. An initial controlled comparison can keep the same old/new proportions while rotating examples; a separate comparison can change the proportions. Changing both simultaneously would obscure whether diversity or balancing helped.

GPU Lexer's promotion policy adds another useful practice: evaluate the actual quantized candidate against a fixed baseline and enforce language-specific regression guards. Its training also includes ordinary rehearsal after targeted corrections.[^7] Apply the same principle to country/script groups, with counts and uncertainty visible. A public aggregate improvement alone is insufficient for promotion.

## 3. Repair supervision where the model lacks useful interpretations

The existing audit established structural validity for many records, but it did not establish semantic correctness of every field. There are incompatible administrative conventions, artificially spaced script samples, incomplete address fragments and known geographic anomalies. Adding more of the same type of row can reinforce the wrong lesson.[^1]

### Preserve uncertainty instead of inventing labels

A source that distinguishes only a broad locality cannot always tell us whether a span is `city`, `suburb` or `city_district` under the product's policy. Similarly, a source that annotates only roads may leave other address text unlabeled. Such positions are not automatically background `O`.

Research on combining partially annotated corpora trains CRFs by summing over label sequences consistent with the annotations that are actually known. This directly addresses the mismatch between differently annotated datasets.[^8] Work on noisy NER labels additionally studies marginalizing low-confidence labels rather than treating every annotation as certain.[^9]

**Recommended adaptation:** retain exact labels where the mapping is defensible; represent an ambiguous span with a bounded set of permissible fields; record truly unannotated regions separately from confirmed background. Preserve known boundaries. For example, an ambiguous locality should remain one known span, not become an unrestricted sequence of unrelated tags. Train against the sum of allowed paths.

This does not recover information the source never contained. It avoids punishing a plausible interpretation simply because that source uses a less detailed schema. A small reviewed, fully labeled set remains necessary to anchor the fine distinctions.

There is an important distinction for the Australian data: the current renderer **omits locality text entirely** because its mapping is unresolved. That is a partial input, not a visible unlabeled locality. Partial-label training only becomes useful there if locality text is reintroduced with an honest set of allowed interpretations.

Keep the full target label vocabulary. A supplementary coarse-field score can help diagnose schema disagreements, but collapsing city, suburb and district in the primary score would change the task and inflate apparent progress.

### Acquire evidence-rich examples for the weak countries

Egypt and India need more complete, natural-looking examples with defensible locality and administrative labels. South Korea needs both ordinary Hangul addresses and Romanized forms, including building, district, road-number and apartment conventions. Their current top-eight results argue against expecting a ranking-only intervention to solve them.

Start with **100 reviewed development examples per priority country** for Egypt, India, South Korea and Taiwan. These are diagnostic targets, not sufficient national test sets. Preserve original text, source identifier, source date, original structured fields, mapping policy, uncertainties and script. Distinguish a missing component from a component present but unlabeled.

Acquire additional records according to demonstrated gaps: complete versus partial address, native versus Romanized script, apartment/floor, rural route, building name, missing separators, and unfamiliar locality. The source-quality audit already identifies candidate sources and their limitations; unrestricted use of every acquired source is not the goal.

The quarantined Chinese address dataset is useful for its explicit annotation guidelines and native-script structure. Its original paper studies dependencies richer than a simple linear label chain.[^10] Review the schema and reuse terms before training on it. Preserve its original train/dev/test assignments if making any comparable research claim; do not fold the published test into a training mixture.

### Use unlabeled text to discover what generated data misses

The existing 2,480 Web Data Commons strings are a starting pool, not enough to characterize worldwide natural input. First deduplicate by address family and site, then select varied strings where the native parser, older checkpoint and new checkpoint disagree. Include a random sample: disagreement-only selection can miss errors shared by every model.

For a first 1,000-example review batch, a proposed allocation is 400 varied disagreements, 300 underrepresented country/script cases and 300 random cases. These counts are experimental choices. Human review should resolve uncertain labels; automatic agreement remains weak supervision, not independent gold.

Create new generated examples from the resulting **failure families**, without reusing protected evaluation strings or address identities. Render the same known components with independently varied order, capitalization, separators and safe omissions. Derive spelling perturbations and spacing styles from observed data, and keep transformation rates modest. Randomly rearranging country/city combinations would generate contradictions rather than useful diversity.

GPU Time's model card explicitly distinguishes generated-corpus scores from evidence on real human language. That distinction should remain central here.[^11] Compilation or round-trip checks prove internal consistency; they cannot prove that a mined sentence or address was interpreted correctly.

## 4. Establish an accuracy reference before demanding extreme compression

Every executed neural run has used approximately 615,000 parameters. There is no measured scaling curve. Neither the present error rate nor the training score proves that this capacity is sufficient or insufficient: incomplete optimization, label noise and representation limits can all produce a plateau.

The existing architecture already permits a straightforward capacity comparison:

| GRU hidden width | Instantiated parameter count | Float32 parameters, gradients and two Adam moments |
| --- | ---: | ---: |
| 144, current | 615,244 | approximately 9.4 MiB |
| 288 | 2,206,444 | approximately 33.7 MiB |
| 480 | 5,876,332 | approximately 89.7 MiB |

These counts were obtained by instantiating the current model. Memory figures are arithmetic estimates at 16 bytes per parameter, **excluding activations, data loading, framework allocations and extra copies**. They are not measured training peaks.

Start the accuracy campaign around **5–10 million parameters**, with planned comparisons around **20 million and 50 million**. These are experimental anchors, not a new ceiling or promised browser sizes. The existing 5.9M configuration is a convenient first implementation; the 2.2M configuration is an optional intermediate measurement, not a gate. Run the small baseline on the same data and supervision for comparison.

Do not require incremental improvements at every size before testing a substantially larger reference. Compare both matched training budgets and development convergence, allowing suitable learning rates and enough data exposure. Start with one model family to isolate capacity; if wider recurrent layers become inefficient, test a character-aware encoder with a different context architecture separately. A single undertrained run is not a scaling result.

Also evaluate the newer Senzing native model as an offline baseline in an isolated resource directory. The existing measured native baseline is the older default resource set and scores 83.79% on this public suite. Upstream libpostal's 99.45% headline comes from a different held-out evaluation and is not a target already demonstrated on these examples.[^12] Senzing's benchmark is also related to its development process, so improvements there must be confirmed independently.[^13]

### Distill useful expertise into one browser model

Once a larger reference is demonstrably better, measure it as a browser candidate. If its download, startup or inference cost warrants a smaller alternative, train a student using both trusted labels and the teacher's distribution over interpretations. Prefer structured distillation that accounts for neighboring labels rather than only copying hard predictions. Research provides tractable CRF distillation objectives using local structural marginals.[^14]

For an identical token lattice and linear-chain factorization, teacher adjacent-label marginals allow the student to learn sequence preferences without enumerating every possible parse. This is especially relevant to the measured ranking gap. If teacher and student use different tokenizations, alignment must be handled explicitly; the simple formula cannot be reused unchanged.

The more ambitious extension is **several specialized offline teachers distilled into one global student**. For example, a teacher trained on native East Asian address structure could supply expertise absent from the global reference. Multilingual sequence-labeling research has investigated combining language-specific teachers in a unified student.[^15] This avoids requiring consumers to download and run every teacher.

Do not build specialist teachers until the single larger reference reveals a persistent regional ceiling. They are a contingent research direction, not a requirement for the first useful model.

No fixed complete-package limit is imposed at this stage. For scale, 5M, 20M and 50M parameters occupy approximately 5, 20 and 50 MB as raw one-byte weights, or 20, 80 and 200 MB as raw float32 weights. Those arithmetic figures exclude quantization metadata, compression, runtime assets and working memory; they are not browser measurements. Compare actual complete packages and their accuracy. A 10–30 MB package is a legitimate candidate to evaluate, rather than a failure by definition. Choose a deployment budget after measuring the tradeoff and intended loading behavior.

## 5. Test a representation that preserves boundaries across scripts

The current model embeds bytes **inside pre-split tokens**, then pools each token before sequence modeling. It is not a raw-byte sequence tagger. The tokenizer splits Han ideographs individually but groups consecutive Hangul letters and many other letters into word-like units; a label boundary inside one of those units is impossible to emit.

A synthetic check makes this concrete: `서울특별시강남구` becomes one eight-character token. A target boundary between `서울특별시` and `강남구` is rejected by the existing encoder. The example demonstrates a representational constraint; it is not a measured estimate of how frequently users omit such spaces. Public Korean failures also include Romanized road/district mistakes, so this tokenizer issue cannot explain all of them.

**Recommended architecture challenger:** construct a small embedding for each Unicode code point from its UTF-8 bytes, preserve spaces and punctuation as sequence positions, encode local patterns with convolution and address context with a small bidirectional GRU, then predict field labels at character boundaries. This reuses most existing machinery while removing hard word boundaries. Preserve the original text and an explicit code-point-to-UTF-16 map for browser offsets.

Compare this challenger with the token model at similar parameter counts. A code-point sequence may be considerably longer, making recurrent computation and CRF decoding more expensive. Measure this cost before introducing downsampling. If needed, retain a full-resolution local path while a downsampled contextual path supplies broader context.

CANINE offers a research precedent for character input with downsampling and reconstruction for sequence prediction. ByT5 supplies evidence that byte input can improve robustness to noisy spelling.[^16][^17] Both are much larger pretrained systems; neither establishes that this small address architecture will win. Their relevance is the representation principle, not a recommendation to ship their checkpoints.

Evaluate native spacing, missing separators, mixed scripts, diacritics, non-ASCII digits and supplementary Unicode characters. Report unsupported inputs and unrepresentable gold spans in the denominator. Do not silently drop difficult strings and then claim a higher accuracy.

The previously failed gap-feature experiment does not settle this question. It prepended gap information to an existing pooled token representation; the proposed challenger changes the sequence units and should be trained as its own controlled model.

## 6. Make accuracy claims and browser constraints real

### Independent evaluation

Construct a reviewed natural-input development set and a separate locked final set before continued tuning can contaminate both. A reasonable first allocation is 500 development addresses, 1,500 locked addresses and 500 separately stratified negatives/ambiguous inputs, with an additional disjoint calibration set for any confidence thresholds. These are proposed starting budgets, not sample sizes sufficient to certify every country at 99%.

Use reviewers capable of reading the relevant scripts and adjudicate policy disagreements. Generated expected spans and model-assisted annotations are valuable training material, but they cannot substitute for independent review in the final accuracy claim. Keep different renderings of the same address and related source records together across splits.

Measure exact ordered fields and source spans, per-field precision/recall, country/script groups, negative false positives, ambiguity behavior and rejected-input coverage. Keep public field-map results separately labeled. Show the instance-weighted aggregate and country-level summaries; neither alone fully describes a global product.

If the model offers a confidence score, calibrate it on disjoint reviewed examples and report error against coverage: how often it is correct among the inputs it accepts, and how many inputs it accepts. Selective-classification research formalizes this tradeoff.[^18] A CRF score or a top-two margin is not automatically a correctness probability, and distribution shifts can invalidate calibration. High accuracy obtained by rejecting most addresses must be stated plainly.

The current prediction status is `unassessed`; non-address recognition and calibrated abstention have not been implemented or validated. An address parser also cannot establish deliverability, locate a building or infer a missing city from no evidence.

### Deployment

The current stored-int8 weight archive is 612,787 bytes, approximately 598 KiB. That is not a finished package. The measured float ONNX export is approximately 2.46 MB raw, and the generic Wasm runtime inspected previously is approximately 13.96 MB raw before its other assets. These are different representations and compression bases.[^1]

Use ONNX Runtime for export correctness and early profiling. First investigate its official reduced-operator Web build rather than immediately writing a new inference engine.[^19] If the measured complete download is still unacceptable, a fixed-architecture JavaScript or Wasm implementation becomes justified. Compare identical trained weights, preprocessing and public results, including close numerical decisions.

QIP's 12.7 kB Wasm highlighter uses a different algorithm from GPU Lexer. Its reported speed advantage on repeated JavaScript does not establish that Wasm accelerates our neural parser.[^20] For one short address, favor a measured CPU path initially; add WebGPU only if batch measurements justify dispatch, transfer and readback overhead. The existing Node/Wasm parity checks establish a useful export milestone, not Safari or Chromium performance on the target Mac.

Qualify the quantized artifact on the full development suite and locked final evaluation, with country-level regressions visible. Current quantization checks cover generated development examples and a small cross-runtime fixture set; public float accuracy must not be presented as quantized browser accuracy.

### M1 Pro with 16 GB RAM

Apple documents PyTorch acceleration through MPS on Apple Silicon.[^21] The 5.9M model is a useful local starting point. For 20M and 50M parameters, float32 parameters, gradients and two Adam moments alone total approximately 320 MB and 800 MB respectively. This does not establish that a particular training configuration fits or runs quickly: activations, long character sequences, dataset materialization and framework allocations can dominate. Measure a full training step and peak memory on the Mac before choosing batch sizes for those runs.

Start with a measured CPU/MPS comparison over a representative training slice, including backward pass and CRF decoding. Current Linux CPU timings—about 374 seconds for the latest 100,000-row, three-epoch training loop—must not be extrapolated as Mac timings. The existing trainer materializes encoded datasets in memory; use bounded batches or compact cached arrays if this becomes the memory bottleneck.

Cloud GPUs become useful if repeated medium-teacher runs or a much larger raw-text pretraining campaign make local iteration too slow. There is no evidence that a cloud GPU is necessary for the next decisive experiments. Do not begin a foundation-model pretraining project before the supervised scaling comparison establishes a reason.

## Execution order and decision gates

The following are proposed experiments. Apart from the diagnostics and parameter counts above, they have not yet been run.

| Order | Experiment | Control | Decision it resolves |
| --- | --- | --- | --- |
| 1 | Capacity comparison: roughly 5–10M, 20M and 50M | Small baseline; same data and supervision, plus convergence comparisons | What accuracy becomes possible with substantially more capacity? |
| 2 | Additional complete-sequence loss | Fixed architecture, data, initialization and updates | Can training recover some of the measured ranking gap? |
| 3 | Correct-reference preservation; combine if useful | Same-size reference, trusted training labels | Can negative flips fall without suppressing new learning? |
| 4 | Rotating exposure, followed by full-pool training | Fixed-subset control at matched presentations | Does broader exposure help, and what happens with enough training on the full pool? |
| 5 | Country/source-aware sampling | Winning exposure policy, same presentation budget | Does balanced rehearsal repair regressions and weak groups? |
| 6 | Character-boundary challenger | Comparable-size token model, identical eligible inputs | Do script-neutral boundaries improve accuracy at acceptable compute cost? |
| 7 | Accurate float and quantized browser candidates | Same model and public output contract | What are the actual size, latency and memory tradeoffs? |
| 8 | Optional distillation | Accurate larger candidate and undistilled student | Is a smaller alternative worth its accuracy loss and engineering cost? |

Use one seed for inexpensive screening and repeat the control and promising variants over at least three seeds before accepting small gains. Avoid stacking all interventions into one run. Evaluate both fixed-budget learning and convergence for the capacity experiment. Select checkpoints using a declared development policy; do not repeatedly select on the locked final set.

In parallel with the first runs, review weak-country examples, establish partial-label mappings and assemble the independent sets. A failed country floor should trigger a targeted investigation, not an automatic return to acquiring more rows. For example, Egypt's current results justify reviewing its administrative annotations before applying a global sampling multiplier.

The immediate milestone is a reproducible improvement in **actual first-choice complete parses**, fewer negative flips, and visible progress on the weak-country development sets. The larger milestone is to outperform the appropriate native baseline on independent inputs with a documented size/latency tradeoff. Ninety-nine percent global accuracy is an ambition to test, not a forecast justified by the current data.

## Sources

External sources inspected September 14, 2026. Repository snapshots are pinned where available. Local measurements refer to the preserved experiment artifacts; research transfers and future thresholds are proposals.

[^1]: Local experiment. [Executed source-quality audit](address-source-quality-audit.md), [current run metadata](../runs/multisource-100k/run.json), [error diagnosis](../runs/multisource-100k/diagnosis.json), and [training history](address-training-results.md). September 2026.
[^2]: Local experiment. [Top-eight diagnostic results](../runs/multisource-100k/rank-diagnosis.json) and [reproducible diagnostic with exhaustive check](../packages/training/src/gpu_address/rank_diagnosis.py). September 14, 2026. The results record checkpoint and benchmark SHA-256 hashes.
[^3]: Local experiment. [Actual training exposure](../runs/multisource-100k/exposure-diagnosis.json) and [trainer](../packages/training/src/gpu_address/train.py). September 14, 2026. Sample reconstruction uses seed 2026, the recorded zero-rejection count and the verified training file hash.
[^4]: Arik Chakma. [GPU Time architecture: focal distillation and sequence loss](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md). Pinned September 2026 snapshot.
[^5]: Sergey Edunov et al. [Classical Structured Prediction Losses for Sequence to Sequence Learning](https://arxiv.org/abs/1711.04956). NAACL 2018.
[^6]: Sijie Yan et al. [Positive-Congruent Training: Towards Regression-Free Model Updates](https://arxiv.org/abs/2011.09161). CVPR 2021.
[^7]: Vercel Labs. [GPU Lexer training and promotion policy](https://github.com/vercel-labs/gpu-lexer/blob/main/packages/training/WEIGHTED-TRAINING.md), inspected September 14, 2026; [pinned model card](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/MODEL_CARD.md).
[^8]: Nathan Greenberg et al. [Marginal Likelihood Training of BiLSTM-CRF for Biomedical Named Entity Recognition from Disjoint Label Sets](https://aclanthology.org/D18-1306/). EMNLP 2018. Evidence concerns biomedical extraction, not postal data.
[^9]: Kun Liu et al. [Noisy-Labeled NER with Confidence Estimation](https://aclanthology.org/2021.naacl-main.269/). NAACL 2021.
[^10]: Hao Li et al. [Neural Chinese Address Parsing](https://aclanthology.org/N19-1346/). NAACL 2019. [Original code, data and annotation-guideline repository](https://github.com/leodotnet/neural-chinese-address-parsing).
[^11]: Arik Chakma. [GPU Time model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md). Pinned September 2026 snapshot. Author-reported measurements and limitations.
[^12]: OpenVenues. [Libpostal README: training and held-out evaluation](https://github.com/openvenues/libpostal). Inspected September 14, 2026.
[^13]: Senzing. [Libpostal data and evaluation](https://github.com/Senzing/libpostal-data). Inspected September 14, 2026.
[^14]: Xinyu Wang et al. [Structural Knowledge Distillation: Tractably Distilling Information for Structured Predictor](https://aclanthology.org/2021.acl-long.46/). ACL 2021.
[^15]: Xinyu Wang et al. [Structure-Level Knowledge Distillation For Multilingual Sequence Labeling](https://aclanthology.org/2020.acl-main.304/). ACL 2020.
[^16]: Jonathan H. Clark et al. [CANINE: Pre-training an Efficient Tokenization-Free Encoder for Language Representation](https://arxiv.org/abs/2103.06874). Preprint 2021; TACL 2022.
[^17]: Linting Xue et al. [ByT5: Towards a token-free future with pre-trained byte-to-byte models](https://arxiv.org/abs/2105.13626). Preprint 2021; TACL 2022.
[^18]: Yonatan Geifman and Ran El-Yaniv. [Selective Classification for Deep Neural Networks](https://arxiv.org/abs/1705.08500). 2017.
[^19]: ONNX Runtime. [Custom builds and reduced operators](https://onnxruntime.ai/docs/build/custom.html) and [Web builds](https://onnxruntime.ai/docs/build/web.html). Inspected September 14, 2026.
[^20]: Patrick G. W. Smith / QIP. [Syntax highlight comparison, pinned page source](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/site/syntax-highlight-comparison.md). September 2026 snapshot. See also [detailed local Wasm/WebGPU review](wasm-webgpu-research.md).
[^21]: Apple Developer. [Accelerated PyTorch training on Mac](https://developer.apple.com/metal/pytorch/). Inspected September 14, 2026. Hardware/backend documentation, not an address-model performance measurement.
