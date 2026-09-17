# gpu-postal model card

Release `0.1.0-experimental.3` is a small **US-only** address parser for WebGPU.
It returns original text and UTF-16 spans for editable forms and highlighting,
including partial and reordered inputs. The seven-country experimental.2 weights
remain available in that release; its evaluation numbers do not describe this model.

## Model and training

154,446 parameters: byte convolutions, two bidirectional affine-scan layers,
seven-field BIO predictions and CRF decoding. Gap features are enabled. GPA3
stores five-bit quantized codes in byte slots, delivered with Brotli; WebGPU
executes restored float32 weights. No CPU fallback or runtime dependencies.

Trained from scratch on all 3,077,917 selected US originals each epoch, using
PyTorch MPS on an M1 Pro with 16 GB memory. Batch 128, seed 2026, AdamW, initial
learning rate .002, weight decay .01. Presentations: 50% original, 25% partial,
15% reordered and 10% combined, plus case augmentation. Fine source spans permit
unit movement and field omission without guessing internal boundaries.

Training completed 26 epochs in 9h 29m and stopped after six epochs without a new
eligible development best. Epoch 20 was selected by mean int5 partial/reordered/
combined development accuracy, subject to clean old-US/new-US guards. Test results
were not used to choose among checkpoints. See the [recipe](packages/training/RETRAINING.md).

The corpus contains 77,917 retained US originals plus 3 million selected from the
existing worldwide-addresses US candidate pool. It is not a full scan of all US
shards. Source/group balancing and split protections were retained. Only 90 rows
have fine PO-box tags, 368 building-name tags and 227 floor tags; unit tags occur
in 696,471 rows. Volume does not imply balanced coverage of address conventions.
Source labels and entity overlap are imperfect. See [notices](THIRD_PARTY_NOTICES.md).

## Output and use

Fields: `street_address`, `locality`, `city`, `district`, `state`, `postcode`,
`country`. Street address includes building, road, unit, floor and PO-box text.
Labels may repeat; components follow input order. Predictions are `unassessed`,
not calibrated confidence. This parses text; it does not verify existence,
deliverability, missing fields or whether the input is an address.

## Evaluation

### Held-out source panels

| Panel | Int5 exact ordered spans |
| --- | ---: |
| Clean | 3,942/4,000 — 98.55% |
| Partial | 975/981 — 99.39% |
| Reordered | 745/756 — 98.54% |
| Partial + reordered | 614/626 — 98.08% |
| ZIP first | 497/500 — 99.40% |

These panels were frozen before training but inspected during the pilot. They
are held-out diagnostics, not a newly blind test or representative US traffic.

### External US NAD comparison

842 frozen structured addresses across 40 states, including 118 with subaddresses:

| Parser | Whole-address field match |
| --- | ---: |
| gpu-postal experimental.3 int5 | 828/842 — 98.34% |
| usaddress 0.5.16 | 831/842 — 98.69% |
| libpostal default | 824/842 — 97.86% |
| Senzing v1.2 | 829/842 — 98.46% |
| Deepparse BPEmb + attention | 815/842 — 96.79% |

The current model was rerun; comparator predictions reuse the original evaluation.
Every field must match after NFKC/casefold tokenization, ignoring commas and
whitespace. Locality joins street and district joins state. Other punctuation,
repeated tokens and extra fields count. This is agreement with registry fields,
not nationwide accuracy. Training overlap with the expanded corpus and competitors
is unknown. The original exclusion check covered the earlier released corpus.

### Partial and shuffled institutional addresses

The same 20 public contact addresses generate these synthetic presentations.
All seven fields are preserved in this scorer, with no locality/district merging.

| Inputs | gpu-postal int5 | usaddress |
| --- | ---: | ---: |
| Complete | 17/20 | 19/20 |
| Shuffled | 368/460 | 24/460 |
| Partial | 163/200 | 156/200 |
| Partial + shuffled | 157/200 | 8/200 |
| Single field | 68/80 | 53/80 |
| Building prefix | 2/16 | 15/16 |
| Messy + partial + shuffled | 10/20 | 0/20 |

Labels were prepared before pilot inference. Cases were then inspected during
development; they are not newly blind. Variants share parents and must not be
pooled as independent observations. They expose order flexibility as a strength
and building/floor/PO-box handling as remaining weaknesses. Float32 matches
411/460 shuffled cases versus int5's 368/460, showing quantization sensitivity in
this difficult sample. We publish the int5 candidate with these trade-offs visible.

On the upstream usaddress US50 diagnostic, coarse-field matches are 675/680 for
gpu-postal and 678/680 for usaddress. Our stricter seven-field exact-span score is
663/680. There are 16 exact training overlaps; entity and competitor exposure are
unknown. This is a historical upstream test, not an independent blind benchmark.

## Size and browser performance

| Measurement | Result |
| --- | ---: |
| Model | 53,353 bytes (Brotli) |
| Model + four JavaScript modules | 58,687 bytes (Brotli) |
| usaddress model, excluding Python/CRFsuite/features | 50,189 bytes (Brotli) |
| Warm parse median / p95 | 5.2 / 8.9 ms |

Both sizes use Brotli quality 11, with each file compressed separately. Website
UI, documentation and HTTP headers are excluded. Serve with `Content-Encoding: br`.
usaddress's model-only number is not a browser application download size.

Timings: Chrome 153, Apple Metal-3 non-fallback adapter, M1 Pro 16 GB; 400 warm
parses per model over four alternating rounds. The old model measured 5.1/9.5 ms
in the same session. Browser/driver caches were not purged; latency varies with
hardware and loading conditions. This is not a CPU-vs-GPU speed comparison.

Python and actual WebGPU predictions matched on all 931 qualification inputs,
including UTF-16, gaps, newlines and reordered cases. Empty input and disposal
checks passed. Device-loss tests are mocked, not a physical GPU reset.

## Evidence and reproduction

[Release evidence](apps/website/public/evaluation-us-v1/README.md) includes all
diagnostic predictions, current NAD predictions, comparator links, hashes and
browser reports. `packages/training/scripts/release_us_evidence.py` rebuilds the
release report from the frozen local checkpoint and diagnostic artifacts.
`packages/core/test/external-benchmark.html` checks the current NAD browser parity.
Raw training data is not shipped in npm.

Model SHA-256: `06a212f708a52c32e099c15e384e3bd149885c01d06c4b00343cc3b7ad894b60`.

Checkpoint SHA-256: `0c294a7ae4ddfce5e0305bf5516c496ae2b30ceca0f37bc3b05f60895aa9dacd`.

## License

Original code and documentation are [MIT](LICENSE). Preserve the model's
[source notices](THIRD_PARTY_NOTICES.md). The US-only model was trained from
scratch, without the earlier release's Australian G-NAF rows; historical notices
remain documented for earlier artifacts. No upstream organization endorses it.

Report issues with public or redacted examples at
[GitHub Issues](https://github.com/f0rr0/gpu-postal/issues).
