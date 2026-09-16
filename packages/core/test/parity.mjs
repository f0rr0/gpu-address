import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { components, decode, encode } from '../dist/contract.js';
import { readModel, WEIGHT_COUNT } from '../dist/model.js';

const [directory] = process.argv.slice(2);
if (!directory) throw new Error('Usage: npm run test:parity -- EXPORT_DIRECTORY');
for (const suffix of [".f32", ""]) {
  const fixture = JSON.parse(fs.readFileSync(path.join(directory, `fixtures${suffix}.json`), "utf8"));
  const model = readModel(fs.readFileSync(path.join(directory, `model${suffix}.bin`)));
  assert.equal(model.weights.length, WEIGHT_COUNT);
  for (const item of fixture) {
    const encoded = encode(item.text, model.gapFeatures);
    assert.deepEqual([encoded.inputs], item.byte_ids, 'JS tokenization differs from Python');
    const labels = decode(item.emissions[0], model.transitions, model.start, model.end);
    assert.deepEqual(labels, item.path, 'JS CRF decoding differs from Python');
    const fields = components(labels, encoded.offsets, item.text);
    const expected = item.components.map(field => ({
      ...field,
      start: Array.from(item.text).slice(0, field.start).join('').length,
      end: Array.from(item.text).slice(0, field.end).join('').length,
    }));
    assert.deepEqual(fields, expected, 'UTF-16 field offsets differ');
  }

  console.log(JSON.stringify({ encoding: suffix ? "float32" : "int8", fixtures: fixture.length, weights: model.weights.length, pathsEqual: true, utf16SpansEqual: true, scope: "Model format, tokenizer, and CRF parity; GPU numerical parity needs a browser" }));
}
