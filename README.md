# gpu-postal

A small neural address parser for the browser. Split an address into fields with
WebGPU in 74.4 kB (Brotli), including the model and runtime, with zero runtime
dependencies. Your input stays on your device.

Use it to turn a pasted address into editable form fields or highlight address
components in text.

## Usage

```sh
npm install gpu-postal@experimental
```

```js
import { createParser } from 'gpu-postal';

const parser = await createParser();
const result = await parser.parse('123 Main Street, Boston MA 02110');

console.log(result.components);
// [
//   { label: 'street_address', raw: '123 Main Street', start: 0, end: 15 },
//   { label: 'city', raw: 'Boston', start: 17, end: 23 },
//   { label: 'state', raw: 'MA', start: 24, end: 26 },
//   { label: 'postcode', raw: '02110', start: 27, end: 32 }
// ]

await parser.dispose(); // when finished with the parser
```

Create one parser and reuse it. Requires a WebGPU browser over HTTPS or localhost;
there is no CPU fallback. The package includes the model. If your bundler doesn't
copy `model.bin`, serve it yourself and call `createParser('/models/model.bin')`.
You can also pass an `ArrayBuffer` or `Uint8Array`.

## Output

`parse(text)` returns `{ status, components, offsetEncoding: 'utf-16' }`.
Each component contains a label, the original text and offsets compatible with
`text.slice(start, end)`. Components follow input order; labels can repeat.

Labels: `street_address`, `locality`, `city`, `district`, `state`, `postcode`,
`country`. Street address includes building, unit, floor and PO-box information.

Successful predictions have `status: 'unassessed'`. Empty or oversized inputs
return `status: 'unsupported'` and an empty component array. Limits are 512 Unicode
code points, 128 tokens and 64 UTF-8 bytes per token; invalid Unicode is unsupported.
GPU and loading failures throw errors.

## Model and performance

We trained the 154,446-parameter model from scratch on 3.79 million addresses from
the US, UK, Australia, New Zealand, Canada, Ireland and English-language South
African sources. It combines byte convolutions, bidirectional scans and CRF
decoding. We quantize weights to five bits, store the codes in byte slots for
Brotli compression, and run inference in float32.

| Measurement | Result |
| --- | ---: |
| Model weights | 69.0 kB (Brotli) |
| JavaScript + weights | 74.4 kB (Brotli) |
| Warm parse latency, median / p95 | 2.9 / 4.5 ms |
| Same-source held-out exact span accuracy | 99.17% |
| External US GeoSearch exact field accuracy | 87.7% |

Sizes use Brotli quality 11 on each built JavaScript file and the model:
74,350 bytes total (Brotli), excluding HTTP headers. Serve with
`Content-Encoding: br` to deliver Brotli-compressed assets.
Browser timings use an M1 Pro, Chromium 152 and 1,000 sequential inputs.
GeoSearch contains synthetic address noise; its score measures complete field
matches after ignoring case, commas and whitespace.

On GeoSearch inputs with all four fields present, the model matched 92.7% of
addresses. This experimental release targets editable field suggestions;
partial inputs and country-level generalization remain areas for improvement.
Address validation and deliverability checks require separate services. See the
[model card](https://github.com/f0rr0/gpu-postal/blob/main/MODEL_CARD.md) for
country results, comparisons and evaluation details.

## Development

Node.js 22+:

```sh
npm ci
npm test
python3 -m http.server 8765 --bind 127.0.0.1
# Open http://localhost:8765/examples/basic.html
```

For the Python training tools (Python 3.11+):

```sh
uv sync --locked
uv run pytest
uv run gpu-postal --help
```

## License

[MIT](https://github.com/f0rr0/gpu-postal/blob/main/LICENSE) for original code.
The included model retains its
[source notices and conditions](https://github.com/f0rr0/gpu-postal/blob/main/THIRD_PARTY_NOTICES.md),
including G-NAF attribution and mailing-use restrictions.

Inspired by [GPU Lexer](https://github.com/vercel-labs/gpu-lexer) and
[GPU Time](https://github.com/arikchakma/gpu-time).
