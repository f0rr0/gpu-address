// Node harness for the same onnxruntime-web Wasm backend used in browsers.
// This verifies backend parity; it is not a Safari/Chromium performance result.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import * as ort from 'onnxruntime-web';
import { decode, encode, components } from '../dist/contract.js';
import { createParser } from '../dist/index.js';

const [directory] = process.argv.slice(2);
if (!directory) throw new Error('Usage: npm run test:parity -- EXPORT_DIRECTORY');
ort.env.wasm.numThreads = 1;
const fixture = JSON.parse(fs.readFileSync(path.join(directory, 'fixtures.json'), 'utf8'));
const decoder = JSON.parse(fs.readFileSync(path.join(directory, 'decoder.json'), 'utf8'));
const session = await ort.InferenceSession.create(fs.readFileSync(path.join(directory, 'model.onnx')), {
  executionProviders: ['wasm'],
});

const parser = await createParser(fs.readFileSync(path.join(directory, 'model.onnx')), decoder);
let maxError = 0;
for (const item of fixture) {
  const { offsets, inputs, width } = encode(item.text, decoder);
  assert.deepEqual([inputs], item.byte_ids, 'JS tokenization/encoding differs from Python');
  const result = await session.run({
    byte_ids: new ort.Tensor('int64', BigInt64Array.from(inputs.flat(), BigInt), [1, inputs.length, width]),
    lengths: new ort.Tensor('int64', BigInt64Array.from([inputs.length], BigInt), [1]),
  });
  const values = Array.from(result.emissions.data);
  const expected = item.emissions.flat(2);
  for (let i = 0; i < values.length; i++) maxError = Math.max(maxError, Math.abs(values[i] - expected[i]));
  const emissions = inputs.map((_, t) => values.slice(t * decoder.labels.length, (t + 1) * decoder.labels.length));
  const labels = decode(emissions, decoder);
  assert.deepEqual(labels, item.path, 'Wasm sequence prediction differs');
  const fields = components(labels, offsets, item.text, decoder);
  const expectedFields = item.components.map(field => ({ ...field,
    start: Array.from(item.text).slice(0, field.start).join('').length,
    end: Array.from(item.text).slice(0, field.end).join('').length,
  }));
  assert.deepEqual(fields, expectedFields, 'UTF-16 field offsets differ');
  assert.deepEqual((await parser.parse(item.text)).components, expectedFields, 'Public API parity differs');
}
assert(maxError < 1e-4, `Wasm logits error ${maxError}`);
const report = { fixtures: fixture.length, maxAbsError: maxError, pathsEqual: true, utf16SpansEqual: true,
  backend: 'onnxruntime-web/wasm under Node; one thread',
  scope: 'Float export parity only; not browser performance or complete package qualification' };
console.log(JSON.stringify(report, null, 2));
await session.release();
await parser.dispose();
await assert.rejects(parser.parse("12 Main St"), /disposed/);
