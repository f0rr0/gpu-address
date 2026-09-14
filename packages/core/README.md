# gpu-address

Experimental address field extraction with ONNX Runtime Web / Wasm. Supply a matching exported `model.onnx` and `decoder.json`; weights are not bundled.

```ts
import { createParser } from 'gpu-address';

const decoder = await fetch('/models/decoder.json').then(r => r.json());
const parser = await createParser('/models/model.onnx', decoder);
const result = await parser.parse('12 Main Street, London');
await parser.dispose();
```

`result.components` contains `{ label, raw, start, end }` with UTF-16 offsets into the original string. Status is `unassessed` for field predictions or `unsupported` for inputs outside the declared limits. It does not confirm validity, existence, country or confidence. Maximum: 512 Unicode code points, 128 tokens, 64 raw UTF-8 bytes per token.

Serve ONNX Runtime's Wasm assets according to your bundler's configuration. Browser startup, download size and responsiveness still require browser testing; the automated parity check currently uses the same Wasm backend under Node. Run inference in a worker when integrating an interactive website.
