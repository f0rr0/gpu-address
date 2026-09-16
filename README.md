# gpu-postal

Tiny, local postal-address field suggestions for the browser. Experimental—not
address validation, geocoding, autocomplete, or a replacement for libpostal.

The frozen **epoch-12 int8 GPA3** model has 154,446 parameters and **154,562 bytes
of weights**. Inference uses WebGPU, with no runtime dependencies, Wasm, inference
server or API key. Review every result before use.

## Use

```sh
npm install gpu-postal@experimental
```

```js
import { createParser } from 'gpu-postal';

const parser = await createParser(); // loads the included weights once
const result = await parser.parse('123 Main Street, Boston MA 02110');
console.log(result.components); // { label, raw, start, end }[]
await parser.dispose();
```

Requires WebGPU and HTTPS or localhost. Bundlers must preserve the adjacent model
asset; alternatively serve the included `model.bin` yourself and pass its URL or
bytes to `createParser`. No CPU fallback. See the [API](packages/core/README.md).

Seven fields: `street_address`, `locality`, `city`, `district`, `state`, `postcode`,
`country`. Results preserve original text and UTF-16 offsets. `unassessed` means
predicted, **not verified**; `unsupported` only describes input limits, not reliable
country/language detection. Missing fields are not completed.

## Evidence, with limits

Trained from scratch on 3,790,046 rows from US, UK, Australia, New Zealand, Canada,
Ireland and English-language South African sources. This is training scope, not
equal accuracy across countries. Proper names are retained. Other countries and
general multilingual inputs are out of scope.

| Check | Result | What it does not establish |
| --- | ---: | --- |
| Same-source heldout int8 | 12,019 / 12,115 (99.21%) | Real-world accuracy |
| External US GeoSearch, actual browser int8 | 879 / 1,000 (87.9%) | Worldwide or natural-traffic accuracy |
| Four fields present / partial | 720 / 770; 159 / 230 | Reliable incomplete-address handling |
| Warm browser median / p95 | 2.2 / 3.2 ms | Other devices, cold startup, GPU superiority |

Timings: 1,000 sequential inputs, M1 Pro 16 GB, Chromium 152, Apple Metal hardware
adapter. Runtime JavaScript plus weights: **174,699 uncompressed body bytes**;
model-only size is not total download size. See the
[model card](MODEL_CARD.md) and [release evidence](docs/evidence/release-qualification-20260917.json).
The float32 comparator scored 879/1,000, Senzing 877/1,000 and Deepparse 752/1,000
on this same diagnostic. This is not evidence of general superiority over either.

The intended experiment is **paste an address → review suggested fields**. Do not
silently use these predictions for shipping or bulk database cleanup. A small
AI-annotated public-address workflow check matched 13/14 inputs, including one
case-only/comma-removal variant per address. It is not human usability evidence.
See [all inputs and sources](docs/evidence/release-workflow-20260917.json).

## Run locally

```sh
npm ci
npm test
python3 -m http.server 8765 --bind 127.0.0.1
# Open http://127.0.0.1:8765/examples/basic.html
```

The [minimal example](examples/basic.html) is a source example, not a hosted product
demo. It uses the real included model; input is not sent to a server for inference.

Python is local training machinery, not required by browser consumers:

```sh
uv sync --locked
uv run pytest
uv run gpu-postal --help
```

Python 3.11+, Node 22+. Training uses PyTorch MPS on the M1 Pro; PyTorch retains
its hardware-aware CPU thread default. The [training recipe](docs/english-seven-release.md)
records the full 12-epoch run and selection criterion. It stopped at its epoch
budget while still improving, not demonstrated convergence.

## License and reporting

Original code/documentation: [MIT](LICENSE), © 2026 Sid Jain. **Model/source-data
notices and restrictions remain applicable**: [third-party notices](THIRD_PARTY_NOTICES.md).
The package is not an unrestricted MIT-only bundle. No raw training corpus is shipped.

[Report a parsing issue](https://github.com/f0rr0/gpu-postal/issues) with a public
or redacted address, expected fields and output. Never post private addresses.
Country results, known failures and source limitations belong in reports, not
hidden behind one headline accuracy number.

[Research history](docs/README.md) · [Learnings](docs/learnings.md) ·
[Historical worldwide closeout](docs/closeout.md)
