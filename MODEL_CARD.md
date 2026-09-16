# gpu-postal model card

gpu-postal parses addresses on the device with a 154,446-parameter neural model.
The browser runtime has zero runtime dependencies and preserves the original text
and character offsets for editable address forms and span highlighting.

Model release: `0.1.0-experimental.2`, epoch 12, five-bit quantization.

## Architecture and training

The model combines ordered byte convolutions, two bidirectional affine-scan layers,
seven-field BIO predictions and CRF decoding. GPA3 stores five-bit quantized values
in signed byte slots, compressed with Brotli for delivery; the runtime
expands them to float32 for WebGPU execution. A parser reuses its GPU resources
across calls and processes requests in sequence.

We trained from scratch on 3,790,046 addresses for 12 shuffled epochs using PyTorch
MPS on an Apple M1 Pro with 16 GB memory. Training took 3.83 hours, with batch size
128, seed 2026, case augmentation and inverse-country-frequency loss weights.
We selected epoch 12 by equal-country mean exact ordered-span validation accuracy:
99.0044%. Validation was still improving at the end of the 12-epoch budget.

| Training source country | Rows |
| --- | ---: |
| US | 77,917 |
| UK | 74,191 |
| Australia | 1,297,093 |
| New Zealand | 1,415,622 |
| Canada | 2,225 |
| Ireland | 50,883 |
| South Africa | 872,115 |

The training scope covers English-form addresses in these seven countries.
Sources include rendered structured records and inherited tagged corpora.
Street-group splits reduce overlap between training and evaluation. Source
concentration, inherited label errors and possible entity overlap affect
generalization. See [source notices](THIRD_PARTY_NOTICES.md) for attribution
and transformations.

## Output

The parser returns seven fields: `street_address`, `locality`, `city`,
`district`, `state`, `postcode` and `country`. Street address includes
premises, road, unit, floor and PO-box information; district remains a separate
field. Each component includes its original text and UTF-16 offsets.

Use the predictions to populate editable fields. The API marks predictions
`unassessed` and provides no calibrated confidence score. Address existence,
deliverability and missing-field completion require separate services.

## Evaluation

On the same-source street-group holdout, the deployed int5 model matched
**12,014 of 12,115 addresses (99.17%)** by exact ordered spans, compared with
12,022 for float32.

### External US addresses

We evaluated the browser model on a frozen 1,000-address GeoSearch sample with
synthetic noise. Counts below require all fields to match, using per-field token
multisets that ignore case, commas and whitespace.

| Input group | Rows | gpu-postal int5 | gpu-postal float32 | Senzing v1.2 | Deepparse BPEmb + attention |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 1,000 | 877 | 879 | 877 | 752 |
| Four fields present | 770 | 714 | 719 | 682 | 741 |
| At least one absent | 230 | 163 | 160 | 195 | 11 |

gpu-postal reached **87.7% overall** and **92.7% on four-field inputs**.
Its overall result matched Senzing on this sample; Senzing performed better on
partial inputs. Compared with the previous int8 release, int5 reduced the model
and runtime payload by 44%, with five fewer holdout matches and two fewer
GeoSearch matches. On GeoSearch, eight inputs improved and ten regressed.

All parsers received the same inputs and field mapping. We excluded three exact
normalized-text training overlaps before sampling. Near-duplicate, entity and
competitor-training overlap remain unknown. These results describe this
synthetic-noise diagnostic rather than natural traffic or worldwide performance.

### Country diagnostics and workflow examples

Previously inspected public Senzing diagnostics, using float32 and the same token
metric, yielded US 2,130/2,233; UK 232/255; Australia 33/76; New Zealand 38/51;
South Africa 39/53. These development diagnostics show stronger US/UK results
and a generalization gap for Australia, New Zealand and South Africa. Canada and
Ireland have no external results here; Canada's same-source test has 115 rows.

An AI-reviewed, US-dominated natural-address diagnostic matched 48/53 inputs.
A separate workflow check matched **13/14 inputs**: seven public institution
addresses plus lowercase, comma-free variants, with AI annotations prepared before
inference. Two of 52 field values needed correction. The failing UK variant placed
“south” in the street instead of “South Kensington”.

These small checks illustrate behavior; they use AI annotations, have unknown
training-entity overlap and do not measure human time savings. Partial addresses
remain a priority for improvement. Other countries and multilingual inputs fall
outside the evaluated scope.

## Browser performance

Measurements use an M1 Pro with 16 GB memory, Chromium 152 and an Apple Metal-3
hardware adapter.

| Measurement | Result |
| --- | ---: |
| Model weights | 69,016 bytes (Brotli) |
| Release JavaScript + weights | 74,350 bytes (Brotli) |
| Parser initialization, localhost | 14.1 ms |
| First parse | 4.5 ms |
| Warm parse median / p95 | 2.9 / 4.5 ms |

Sizes sum each release file compressed at Brotli quality 11, excluding HTML,
documentation and HTTP headers. Serve with `Content-Encoding: br` for these
transfer sizes.

Warm timings cover 1,000 sequential GeoSearch calls. Initialization measurements
retain browser/driver shader caches and use localhost delivery. Hardware,
browser and loading conditions affect latency; this evaluation covers Chromium
on the M1 Pro, without a CPU comparison.

Int5 browser predictions matched Python components and UTF-16 offsets on all
12,115 holdout and 1,000 GeoSearch inputs. The browser workflow check matched
13/14 inputs. During 1,014 parses after asset loading,
the qualification page recorded zero resource requests under a same-origin CSP.
The example performs inference on the device and includes no telemetry.

## Artifacts and reproduction

Model SHA-256:
`e97cfb86c5ec703ad70ba684f2f373a44dc9c9e1018e517ab6799e74aa5ce84a`.

Checkpoint SHA-256:
`436dc0a84fca3816a851f28a5eb56d716153acc993748ddc16768e7c6502e7ec`.

The release tag preserves the
[training recipe](https://github.com/f0rr0/gpu-postal/blob/v0.1.0-experimental.1/docs/english-seven-release.md)
and [GeoSearch preparation and comparator reproduction](https://github.com/f0rr0/gpu-postal/blob/v0.1.0-experimental.1/docs/evidence/geosearch-sample-20260916.py).
Use `packages/core/test/release.html` for browser qualification.
Training and external evaluation require the corresponding local datasets;
the package includes the model, not the raw corpus.

## License

Original code and documentation use [MIT](LICENSE). Preserve
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) with the weights, including G-NAF
attribution and its requirement for secondary-source deliverability verification
when generating mailing addresses.

Report parsing issues with public or redacted examples at
[GitHub Issues](https://github.com/f0rr0/gpu-postal/issues).
