import { InferenceSession, Tensor } from 'onnxruntime-web';
import { components, decode, encode, validateDecoder, type Component, type Decoder } from './contract.js';
export type { Component, Decoder } from './contract.js';

export interface ParseResult {
  status: 'unassessed' | 'unsupported';
  components: Component[];
  offsetEncoding: 'utf-16';
}

/** Pass a model URL or bytes and its matching decoder.json. No model is bundled. */
export async function createParser(model: string | Uint8Array, decoder: Decoder) {
  validateDecoder(decoder);
  // Own the metadata so caller mutation cannot silently change the parser.
  const config = structuredClone(decoder);
  const options = { executionProviders: ['wasm'] };
  const session = typeof model === 'string'
    ? await InferenceSession.create(model, options)
    : await InferenceSession.create(model, options);
  let closed = false;
  return {
    async parse(text: string): Promise<ParseResult> {
      if (closed) throw new Error('Parser has been disposed');
      const encoded = encode(text, config);
      if (!encoded) return { status: 'unsupported', components: [], offsetEncoding: 'utf-16' };
      const { inputs, width, offsets } = encoded;
      const output = await session.run({
        byte_ids: new Tensor('int64', BigInt64Array.from(inputs.flat(), BigInt), [1, inputs.length, width]),
        lengths: new Tensor('int64', BigInt64Array.from([inputs.length], BigInt), [1]),
      });
      try {
        const tensor = output.emissions;
        if (!tensor || tensor.type !== 'float32' || tensor.dims.join(',') !== `1,${inputs.length},${config.labels.length}`) {
          throw new Error('Model output does not match decoder contract');
        }
        const values = Array.from(tensor.data as Float32Array);
        if (!values.every(Number.isFinite)) throw new Error('Non-finite model output');
        const emissions = inputs.map((_, t) => values.slice(t * config.labels.length, (t + 1) * config.labels.length));
        return { status: 'unassessed', components: components(decode(emissions, config), offsets, text, config), offsetEncoding: 'utf-16' };
      } finally {
        for (const tensor of Object.values(output)) tensor.dispose();
      }
    },
    async dispose() {
      if (!closed) { closed = true; await session.release(); }
    },
  };
}
