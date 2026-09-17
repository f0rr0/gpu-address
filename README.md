# gpu-postal

A small US address parser for the browser. Split full, partial or shuffled addresses into fields with
WebGPU in 58.7 kB (Brotli), including the model and runtime, with zero runtime
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

We trained the 154,446-parameter model from scratch on 3.08 million US addresses,
with field omission, reordering and case augmentation. It combines byte convolutions, bidirectional scans and CRF
decoding. We quantize weights to five bits, store the codes in byte slots for
Brotli compression, and run inference in float32.

| Measurement | Result |
| --- | ---: |
| Model weights | 53.4 kB (Brotli) |
| JavaScript + weights | 58.7 kB (Brotli) |
| Warm parse latency, median / p95 | 5.2 / 8.9 ms |
| Same-source held-out exact span accuracy | 98.55% |
| External US NAD whole-address field match | 98.34% |

Sizes use Brotli quality 11 on each built JavaScript file and the model:
58,687 bytes total (Brotli), excluding HTTP headers. Serve with
`Content-Encoding: br` to deliver Brotli-compressed assets.
Browser timings use an M1 Pro, Chrome 153 and 400 warm parses per model in four
alternating rounds. The 842-address NAD sample measures complete field matches
after ignoring case, commas and whitespace; localities join street, districts join state.

### Compared with usaddress

| Diagnostic | gpu-postal int5 | usaddress 0.5.16 |
| --- | ---: | ---: |
| US NAD, full addresses | 828/842 | 831/842 |
| Shuffled institutional addresses | 368/460 | 24/460 |
| Partial | 163/200 | 156/200 |
| Partial + shuffled | 157/200 | 8/200 |
| Building prefixes | 2/16 | 15/16 |
| Model only | 53.4 kB (Brotli) | 50.2 kB (Brotli) |

Both sizes use Brotli quality 11 and exclude runtimes. usaddress requires Python,
CRFsuite and feature-extraction code. The institutional cases derive from 20
public addresses, with labels prepared before pilot inference; variants are not
independent observations. Their scorer preserves all seven fields. The NAD
benchmark uses the coarser mapping above. Training overlap is not fully known.

This experimental release targets editable field suggestions. Order flexibility
is a strength; building names, floors and some PO boxes still need correction.
Address validation and deliverability require separate services. See the
[model card](https://github.com/f0rr0/gpu-postal/blob/main/MODEL_CARD.md) for
training, comparisons and evaluation details.

The [release evidence](apps/website/public/evaluation-us-v1/README.md) publishes
inputs, predictions, sizes and browser checks. The current model is US-only;
the previous seven-country model remains available as `0.1.0-experimental.2`.

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

The Next.js demo lives in `apps/website`: `npm run dev:website` locally,
`npm run build:website` for a production build. On Vercel, select Next.js,
set the root directory to `apps/website`, and enable access to files outside
that directory for the core workspace. The demo serves the model with Brotli
content encoding; the website itself is not included in the package-size figure.

Current website comparison data is at `/evaluation-us-v1/results.json`.
Historical evaluations remain available with their original model versions.

## License

[MIT](https://github.com/f0rr0/gpu-postal/blob/main/LICENSE) for original code.
The included model retains its
[source notices and conditions](https://github.com/f0rr0/gpu-postal/blob/main/THIRD_PARTY_NOTICES.md),
with inherited dataset attribution. Historical G-NAF notices are retained for earlier releases.

Inspired by [GPU Lexer](https://github.com/vercel-labs/gpu-lexer) and
[GPU Time](https://github.com/arikchakma/gpu-time).
