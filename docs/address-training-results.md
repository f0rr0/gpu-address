# Address data preparation and first training campaign

Run date: September 14, 2026. This document records executed experiments, rather than proposed targets. Code and reproduction commands are in [the experiment directory](../README.md).

Follow-up: [the accuracy-improvement campaign](address-accuracy-improvements.md) retains a same-size continuation checkpoint at **75.71% public agreement**, diagnoses its regressions, and rejects a whitespace-cue variant. The results below preserve the first campaign unchanged.

## What is prepared

The corrected corpus contains **105,000 distinct imported labeled strings**, drawn equally from bounded portions of the OSM-derived, OpenAddresses-derived, and Senzing-specific tagged archives. These are existing generated/tagged examples, not independently collected user inputs.

After grouping, splitting, augmentation, and overlap removal, the corrected version contains **200,699 training examples** and **22,585 development examples**. The 100,000-example training runs use a seeded subset of the training partition and a seeded 6,000-example development subset. Those counts include variants; they are not counts of distinct physical addresses.

Separately prepared:

| Collection | Count | Label status and use |
| --- | ---: | --- |
| Real website address strings | 2,480 | Original WDC street-address literals; retained unchanged and unlabeled |
| Teacher-labeled copies | 2,480 | Native libpostal predictions, never presented as independent gold |
| Teacher labels aligned to raw spans | 2,307 | Exact raw-text alignment; semantic correctness remains unverified |
| Teacher alignment review | 173 | No fabricated spans; retain normalized teacher components for inspection |
| Blind real-input annotation queue | 200 | A subset of the 2,480 strings, not additional examples or completed annotations |
| Fresh NYC structured records/renderings | 1,000 | Provider fields rendered into known spans; staged pending mapping review and deduplication |
| Real prose for address-presence review | 500 | Enron paragraphs; not automatically declared negative |
| Authored negative regressions | 8 | Explicit non-address fixtures; not a production false-positive benchmark |
| Public Senzing benchmark | 12,868 | Existing field labels across 88 country codes; kept out of training |

The real-data and additional staging collections have not yet been mixed into model training. Generated formatting variants and real messy strings remain distinguishable in every record. Every downloaded source has a URL, hash, byte count, and sampling description. Native teacher binaries and resource archives are hashed too.

The sources are bounded compressed prefixes. Shuffling their contents does not make them globally representative. The imported training partition contains 174 country codes, but many have only a handful of examples: **India has 49 original training records**. Country presence is not evidence of supported accuracy.

## What was trained

The model uses UTF-8 byte embeddings and a small convolution to encode each token, followed by two bidirectional GRU layers and a BIO-constrained CRF. It has **615,244 trainable parameters**. There is no pretrained language model, geographic lookup table, or country hint in the forward pass.

The tokenizer splits punctuation and individual CJK ideographs while retaining source offsets. Limits are 512 Unicode code points per input, 128 tokens, and 64 UTF-8 bytes per token. Unsupported inputs are rejected rather than silently truncated. No current generated train/development example exceeded these limits.

Training ran on **Linux x86-64 CPU, four PyTorch threads**, not the M1 Pro. PyTorch 2.14.0 CPU and Python 3.11.15 were used. The scripts support selecting MPS, but Mac execution has not been measured.

Each run retains weights, optimizer/RNG state, seed, configuration, data hashes, and metrics. Exact source snapshots and an environment listing are archived for the two larger runs. Best checkpoints are selected by generated development exact-span accuracy, not public-benchmark performance.

## Measurements

| Run | Training examples / epochs | Generated dev exact spans | Fixed public benchmark field agreement | Training loop time |
| --- | --- | --- | --- | --- |
| `pipeline-20k` | 20,000 / 2 | 71.73% on 1,500 examples | 52.35% (6,736 / 12,868) | 59.4 seconds |
| `international-100k`, coupled augmentation control | 100,000 / 3 | 83.90% on 6,000 examples | 48.18% (6,200 / 12,868) | 430.4 seconds |
| **`independent-layout-100k`, corrected augmentation** | **100,000 / 3** | **84.22% on 6,000 examples** | **74.35% (9,567 / 12,868)** | **390.8 seconds** |
| Native libpostal baseline | No retraining | Not measured here | 83.79% (10,782 / 12,868) | Not comparable to training time |

Training time excludes source acquisition, preprocessing and export. Different generated development sets were used across dataset versions; their percentages are not a fixed-test comparison. The public benchmark is fixed across runs.

The corrected run improves public-benchmark agreement by **26.17 percentage points** over the coupled control, while retaining an approximately **9.44-point gap** to the native baseline. It remains far from the proposed 99% independently validated accuracy target.

For the corrected checkpoint:

| Export measurement | Observed result |
| --- | --- |
| Compressed stored-int8 weights, NPZ | **613,035 bytes (598.67 KiB)**; excludes inference runtime |
| Float ONNX | 2,463,168 bytes; 2,255,317 bytes with Brotli |
| Float vs stored-int8 generated dev exact score | 84.2167% vs 84.2333% |
| Quantization changes across 6,000 dev examples | 12 outputs changed; 1 newly incorrect, 2 newly correct |
| PyTorch vs ONNX CPU maximum fixture emission difference | 0.00001049; decoded paths agree |
| PyTorch vs web Wasm maximum fixture emission difference | 0.00000859; all 26 decoded paths and UTF-16 spans agree |

Int8 is a storage experiment with dequantized inference, not an integer-compute speed claim. Its slight aggregate gain does not erase the newly broken example. The float checkpoint remains the reference. Wasm measurements used ONNX Runtime Web 1.29.0 under Node; no actual Safari/Chromium benchmark was run.

**These metrics must stay separate.** Generated development scores require the complete ordered component list and raw spans to match. The public benchmark has one column per field, so it is scored by exact field-map agreement after NFKC, casefolding, and whitespace normalization. It is not an exact-span test and should not be compared numerically with the development score.

The native baseline uses original libpostal code revision `25099c506612b34b23b1bfe286ca6321fcf06f35` and default v1.0.0 resource archives. It scores **10,782 / 12,868 = 83.79%** on this public benchmark under our stated comparison. This is not Senzing's newer v1.2 model and not a reproduction of a project's headline accuracy figure.

## A failure found and corrected during the campaign

The first augmentation implementation coupled casing and separators: a lowercase variant also inserted commas between every field. The larger control run improved generated development accuracy while regressing on the public benchmark, particularly US examples.

Inspection found ordinary lowercase inputs such as city/state/postcode sequences being merged or assigned the wrong field. We changed the generator so **case, separator layout, and omission are independently sampled**, preserving source gaps in one layout and including spaces-only and mixed layouts. A regression check now requires all nine case/layout combinations to occur. Compact CJK variants additionally remove artificial spaces between ideographs while preserving labels.

The corrected run holds architecture, seed, optimizer, training quota, and epoch count constant. It is a useful augmentation comparison, but not a perfectly matched statistical ablation: rebuilding variants changes some deduplication results and the sampled training examples. The measured improvement supports the augmentation diagnosis without isolating every contributing change. Generated development text also changes; the public benchmark stays fixed. The public benchmark has now influenced debugging and is explicitly development evidence, not an untouched final test.

## What was verified

- All prepared training/development spans reconstruct the labeled raw fields exactly, before and after augmentation.
- No recorded street-group or normalized-string overlap between training and development. No normalized-string overlap with the public benchmark in either partition.
- Last-slash parsing of tagged tokens, separator handling, individual CJK tokenization, and page-scoped RDF provenance.
- CRF partition/loss and best-path decoding match brute-force enumeration on a tiny example; padded batches match single-example inference.
- A small model can overfit a fixture; larger runs produce finite, decreasing losses.
- Float ONNX predictions match PyTorch on export fixtures, including varied lengths; the export harness also tests mixed-length batches.
- The web Wasm harness checks independently implemented JS tokenization, CRF decoding, raw text, and UTF-16 offsets, including a non-BMP character. It runs under Node, not Safari or Chromium.

## What remains before a final browser model

1. **Independent real-input labels.** The 200-row review queue is prepared, but independent human annotation/adjudication is not complete. Teacher predictions and model self-review cannot replace it.
2. **Broader, better balanced sources.** Sparse countries, units/floors, building names and administrative distinctions need more trustworthy examples. Original source identity is missing in some upstream corpora, so current grouping cannot prove all geographic overlap is absent.
3. **Non-address and ambiguity behavior.** The field tagger is not a trained presence detector. The CLI reports `status: unassessed`; no rejection accuracy is claimed. Partial generated inputs can also admit multiple reasonable interpretations that a single inherited label does not capture.
4. **A complete small browser package.** Stored-int8 weight size excludes runtime, tokenizer and decoder. The general-purpose web runtime used for parity is not the final size solution. Its installed standard Wasm binary alone is 13,961,845 uncompressed bytes. No complete-package size target has been met.
5. **Final qualification.** Multiple training seeds, calibration, a fresh locked test, Mac CPU/MPS checks, and actual Safari/Chromium measurements are still required. There is no 99% accuracy or shipping-readiness claim.

No checkpoint from this campaign should be called a finished libpostal replacement. The useful outcome is a reproducible data/training/export pipeline and measured evidence about where it fails.

## Local artifacts

- [Corrected training corpus manifest](../data/layout-independent/manifest.json).
- [Latest float checkpoint](../runs/independent-layout-100k/best.pt).
- [Machine-readable export and evaluation report](../runs/independent-layout-100k/export/report.json).
- [Wasm parity report](../runs/independent-layout-100k/export/wasm-check.json).
- [Real-input teacher-labeling provenance](../data/expanded/teacher-labeling.json).
- [Reproduction commands and file map](../README.md).

Data and checkpoint links point to locally retained, Git-ignored artifacts. The Markdown and source scripts are reviewable repository changes; nothing has been committed or published.
