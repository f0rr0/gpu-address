# gpu-postal

Experimental address field suggestions using WebGPU. Includes the frozen
154,562-byte epoch-12 int8 GPA3 model; no runtime dependencies, Wasm or remote inference.

```js
import { createParser } from 'gpu-postal';
const parser = await createParser();
const result = await parser.parse('123 Main Street, Boston MA 02110');
console.log(result.components);
await parser.dispose();
```

Load once, reuse, then dispose. Calls are serialized through one GPU device and
buffer set. `createParser(source)` also accepts a model URL string, `ArrayBuffer`
or `Uint8Array`. The default resolves `../model.bin` relative to `dist/index.js`.
Bundlers must retain/copy this asset; if yours does not, serve the included
`model.bin` explicitly and use `createParser('/models/model.bin')`.

Fields: `street_address`, `locality`, `city`, `district`, `state`, `postcode`,
`country`. Each component is `{ label, raw, start, end }`, with UTF-16 offsets into
the original string. Do not collapse repeated spans or discard the original input.

`status: 'unassessed'` means field suggestions, not confirmed validity, existence,
country or confidence. `status: 'unsupported'` means outside input limits: at most
512 Unicode code points, 128 tokens and 64 UTF-8 bytes per token; empty or invalid
Unicode input is also unsupported. It is not a reliable unsupported-country detector.

Requires WebGPU and a secure browser context (HTTPS or localhost), with no CPU
fallback. The stored int8 weights are dequantized to float32; this is not native
int8 GPU arithmetic. The architecture is `ordered-byte-conv32-scan128-v3-seven`,
154,446 parameters; old GPA1/GPA2 models are rejected.

Training scope: US, UK, AU, NZ, CA, IE, English-language ZA. Quality is uneven;
incomplete addresses are a known weakness. Intended for reviewable field suggestions,
not shipping validation, geocoding, missing-field completion or autonomous cleanup.

Original code is MIT. Included model/source terms are preserved in
`THIRD_PARTY_NOTICES.md`, including G-NAF attribution and mailing conditions.
See `MODEL_CARD.md` for measurements and limitations.

Source and minimal browser example: https://github.com/f0rr0/gpu-postal
