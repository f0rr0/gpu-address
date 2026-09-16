# gpu-postal — epoch 12 research release

Version: `0.1.0-experimental.1`. Selected by equal-country mean exact ordered-span
validation, not by external benchmark performance. Frozen model SHA-256:
`4ca878842b0eef37037f9ca5fa8f77096b54bb5ff34c42d4c3927d99b7a65624`.
Checkpoint SHA-256:
`436dc0a84fca3816a851f28a5eb56d716153acc993748ddc16768e7c6502e7ec`.

## Intended use and contract

Reviewable field suggestions from one address in a browser. Preserve the original
input and let people correct predictions. This is not a validator, geocoder,
address-presence detector, language detector, or missing-field completer.

Seven fields: street_address (premises/road/unit/floor/PO-box information), locality,
city, district, state, postcode, country. District is not merged into city. Original
spans use JavaScript UTF-16 offsets. Predictions are `unassessed`, not confidence-rated.

English-form addresses from US, UK, AU, NZ, CA, IE and ZA are the training scope.
This does not establish equal performance in those countries. India and worldwide
Latin-script address support are not claimed. Partial inputs can fail badly.

## Training and architecture

154,446 parameters: ordered byte convolution, two bidirectional affine-scan layers,
seven-field BIO emissions and CRF decoding. GPA3 int8 storage is expanded to float32
for WebGPU execution. One parser keeps its resources resident and serializes calls.

Trained from scratch on 3,790,046 rows, 12 full shuffled epochs, seed 2026, batch 128,
MPS on Apple M1 Pro 16 GB, case augmentation and inverse-country-frequency loss
weights. Runtime 13,772.94 seconds. Best validation country-macro exactness 99.0044%.
The 12-epoch budget ended while validation was improving; not proven convergence.

Training counts: US 77,917; GB 74,191; AU 1,297,093; NZ 1,415,622; CA 2,225;
IE 50,883; ZA 872,115. Data is source-concentrated and partly generated, with
inherited annotation errors. Group splitting reduces street overlap but does not
guarantee entity-level independence. Source attribution and transformations:
`THIRD_PARTY_NOTICES.md`. No raw corpus is included.

## Accuracy

Same-source street-group holdout, exact ordered spans: int8 **12,019/12,115
(99.2076%)**, float32 12,022/12,115. This is not real-world accuracy; Canada's test
slice has only 115 rows.

Frozen external US GeoSearch sample (1,000), actual browser int8:

| Group | Rows | Browser int8 | Float32 | Senzing v1.2 | Deepparse BPEmb + attention |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 1,000 | 879 | 879 | 877 | 752 |
| Four fields present | 770 | 720 | 719 | 682 | 741 |
| At least one absent | 230 | 159 | 160 | 195 | 11 |

Metric: exact per-field token multisets, case/commas/whitespace ignored; not ordered
span accuracy. Same inputs and field mapping for all parsers. Three normalized-text
training overlaps were excluded before sampling; near/entity and competitor overlap
remain unknown. Upstream inputs use synthetic noise, not natural production traffic.
The two-case overall difference versus Senzing does not establish superiority.
Quantization changed two field outputs, with one gain and one loss.

Previously inspected public Senzing diagnostics (float32, same token metric):
US 2,130/2,233; GB 232/255; AU 33/76; NZ 38/51; ZA 39/53. CA/IE absent.
These are not blind benchmarks; the weak AU/NZ/ZA results must not be hidden by
the same-source score. Natural AI-reviewed in-scope diagnostics: 48/53, tiny and
US-dominated, not independent human gold.

Fresh workflow spot check: seven public institution addresses and seven lowercase,
comma-free variants, annotated by AI before inference, **13/14** exact field matches.
Two field values needed correction out of 52 fields to enter; all outputs still
require review. The failing UK variant assigns “south” to the street rather than
“South Kensington”. This convenience sample is not a usability study, country
benchmark, or measured time-saving result. Training entity overlap is unknown.

## Browser size, performance and privacy

On M1 Pro 16 GB, Chromium 152, Apple Metal-3 non-fallback adapter:

- Weights: 154,562 bytes. Four runtime JS modules: 20,137 bytes. Total uncompressed
  body payload: **174,699 bytes**, excluding HTML, documentation and HTTP overhead.
- First parser instance initialization: 17.5 ms; first parse: 5.4 ms on localhost.
  Browser/driver shader caches were not purged. **Not a cold internet-load claim.**
- 1,000 subsequent sequential GeoSearch calls: median 2.2 ms, p95 3.2 ms.
  No batch-throughput or CPU-speedup claim.
- Existing float/int8 parity: 29/29 fixtures matched components, UTF-16 offsets
  and reconstructed BIO paths; fixture parity is not exhaustive accuracy.
- Qualification page recorded zero resource requests during 1,014 parses after
  assets loaded, under a same-origin CSP. The source example has no telemetry.
  No public hosted product demo has been deployed or privacy-audited.

Safari, Firefox, mobile GPUs and unsupported-browser fallback are not qualified.

## Reproduce and license

See the repository's `docs/english-seven-release.md` for training and
`packages/core/test/release.html` for browser qualification. GeoSearch preparation
and comparator reproduction are in `docs/evidence/geosearch-sample-20260916.py`.
Selected local data must be reconstructed separately; this is not a bundled corpus
or a claim that a clean clone reproduces all training inputs with one command.

Our code/documentation is MIT. Preserve `THIRD_PARTY_NOTICES.md` with the weights:
this is **not an unrestricted MIT-only model bundle**. G-NAF mailing conditions
require a secondary source for mail-deliverability verification; this model does
not provide it. Source-level provenance limitations remain disclosed.

Please report only public or redacted examples at
https://github.com/f0rr0/gpu-postal/issues. Do not submit private addresses.
