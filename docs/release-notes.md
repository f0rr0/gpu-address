# gpu-postal 0.1.0-experimental.1

A tiny postal-address parser that runs locally in the browser with WebGPU.
154,446 parameters; 154,562 bytes of included weights; no runtime dependencies,
Wasm, inference server or API key.

This is an experimental **field-suggestion tool**, not address validation or a
libpostal replacement. Review predictions before use.

## Try it

The release archive `gpu-postal-0.1.0-experimental.1.tgz` contains the browser
package, exact weights, model card and license notices. Install it directly:

```sh
npm install https://github.com/f0rr0/gpu-postal/releases/download/v0.1.0-experimental.1/gpu-postal-0.1.0-experimental.1.tgz
```

```js
import { createParser } from 'gpu-postal';
const parser = await createParser();
const result = await parser.parse('123 Main Street, Boston MA 02110');
console.log(result.components);
await parser.dispose();
```

WebGPU and HTTPS/localhost required; retain the adjacent model asset when bundling,
or pass an explicit model URL. Clone the repository and run its `examples/basic.html`
for a minimal working browser example. No polished hosted demo or video is part of
this release.

## What we measured

- Actual-browser int8 GeoSearch exactness: **879/1,000**. Four fields present:
  **720/770**; incomplete: **159/230**. Synthetic US diagnostic, not natural traffic.
- The same sample scored 879 with our float32 model, 877 with Senzing and 752 with
  Deepparse. This does **not** establish general superiority.
- Warm median/p95 **2.2/3.2 ms** over 1,000 sequential inputs on M1 Pro 16 GB,
  Chromium 152, real Apple Metal hardware adapter. Not a universal speed claim.
- Runtime JavaScript + weights: **174,699 uncompressed bytes**, excluding HTML,
  documentation and HTTP overhead. Model-only size is not total download size.
- Seven freshly collected public addresses plus seven mechanical messy variants:
  **13/14** matched AI annotations; the failed UK variant put “south” in the street
  instead of “South Kensington”. No human time-saving claim.

Training covers US, UK, AU, NZ, CA, IE and English-language ZA, but accuracy is
uneven: public AU/NZ/ZA diagnostics remain weak, and Canadian evaluation is small.
The model card includes these results, same-source scores and known limitations.

## Artifacts and terms

The model was trained from scratch for 12 full epochs on 3,790,046 rows and chosen
by country-macro validation. Training stopped at its epoch budget, not demonstrated
convergence. No further training is scheduled for this release.

Weights, original checkpoint, model card, browser evidence, source-data manifest
and SHA-256 checksums are attached. `epoch-12.pt` is a PyTorch checkpoint; only load
checkpoints from sources you trust. Raw training/evaluation corpora are not included.

**Original code/documentation: MIT.** Model source conditions remain preserved in
`THIRD_PARTY_NOTICES.md`, including G-NAF attribution and mailing-use conditions.
This is not an unrestricted MIT-only bundle.

Please report public or redacted parsing examples with expected fields and output.
Do not submit private addresses. Thanks to the libpostal, Senzing, Deepparse,
OpenStreetMap, OpenAddresses and G-NAF communities, and GPU Lexer / GPU Time for
inspiration.
