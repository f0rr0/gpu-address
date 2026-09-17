import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createParser } from '../dist/index.js';
import { encode, labels, tokenize } from '../dist/contract.js';
import { readModel, WEIGHT_COUNT } from '../dist/model.js';

const TENSORS = 24;

test('GPU failures release initialization resources and reject active and queued parses', async t => {
  const globals = ['navigator', 'GPUBufferUsage', 'GPUMapMode'];
  const descriptors = globals.map(name => Object.getOwnPropertyDescriptor(globalThis, name));
  t.after(() => globals.forEach((name, i) => {
    if (descriptors[i]) Object.defineProperty(globalThis, name, descriptors[i]);
    else delete globalThis[name];
  }));
  Object.defineProperty(globalThis, 'GPUBufferUsage', { configurable: true, value: {
    STORAGE: 1, COPY_DST: 2, UNIFORM: 4, COPY_SRC: 8, MAP_READ: 16,
  } });
  Object.defineProperty(globalThis, 'GPUMapMode', { configurable: true, value: { READ: 1 } });

  for (const failure of ['shader', 'pipeline', 'buffer', 'bindings', 'loss']) {
    let lose, mapStarted, rejectMap;
    let destroyed = 0, unmapped = 0, submissions = 0;
    const mapping = new Promise(resolve => { mapStarted = resolve; });
    const device = {
      lost: new Promise(resolve => { lose = resolve; }),
      destroy() { destroyed++; },
      createShaderModule() {
        return { async getCompilationInfo() {
          return { messages: failure === 'shader' ? [{ type: 'error', message: 'shader failure' }] : [] };
        } };
      },
      async createComputePipelineAsync() {
        if (failure === 'pipeline') throw new Error('pipeline failure');
        return { getBindGroupLayout() {} };
      },
      createBuffer() {
        if (failure === 'buffer') throw new Error('buffer failure');
        return {
          destroy() {},
          mapAsync() {
            mapStarted();
            return new Promise((_, reject) => { rejectMap = reject; });
          },
          unmap() { unmapped++; },
        };
      },
      createBindGroup() { if (failure === 'bindings') throw new Error('bindings failure'); },
      queue: { writeBuffer() {}, submit() { submissions++; } },
      createCommandEncoder() {
        return {
          beginComputePass() { return { setPipeline() {}, setBindGroup() {}, dispatchWorkgroups() {}, end() {} }; },
          copyBufferToBuffer() {}, finish() {},
        };
      },
    };
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {
      gpu: { async requestAdapter() { return { async requestDevice() { return device; } }; } },
    } });
    if (failure !== 'loss') {
      await assert.rejects(createParser(modelBytes(0)), new RegExp(`${failure} failure`));
      assert.equal(destroyed, 1);
      continue;
    }
    const parser = await createParser(modelBytes(0));
    const active = assert.rejects(parser.parse('123 Main St'), /WebGPU device lost.*test loss/);
    const queued = assert.rejects(parser.parse('London'), /WebGPU device lost.*test loss/);
    await mapping;
    lose({ reason: 'unknown', message: 'test loss' });
    rejectMap(new Error('mapping failed'));
    await Promise.all([active, queued]);
    await assert.rejects(parser.parse(''), /WebGPU device lost/);
    assert.equal(submissions, 1);
    assert.equal(unmapped, 1);
    await parser.dispose();
    await parser.dispose();
    assert.equal(destroyed, 1);
  }
});

test('release weights are frozen and unavailable WebGPU fails before downloading', async () => {
  const bytes = readFileSync(new URL('../model.bin', import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),
    '06a212f708a52c32e099c15e384e3bd149885c01d06c4b00343cc3b7ad894b60');
  assert.equal(readModel(bytes).weights.length, 154446);
  await assert.rejects(createParser(), /WebGPU is unavailable/);
});

function modelBytes(encoding, gapFeatures = 0, magic = 'GPA3') {
  const header = 20 + (encoding === 1 ? TENSORS * 4 : 0);
  const bytes = new Uint8Array(header + WEIGHT_COUNT * (encoding === 0 ? 4 : 1));
  const view = new DataView(bytes.buffer);
  bytes.set([...magic].map(char => char.charCodeAt(0)));
  view.setUint32(4, 1, true);
  view.setUint32(8, encoding, true);
  view.setUint32(12, TENSORS, true);
  view.setUint32(16, gapFeatures, true);
  if (encoding === 0) view.setFloat32(header, -1.25, true);
  else if (encoding === 1) {
    for (let tensor = 0; tensor < TENSORS; tensor++) view.setFloat32(20 + tensor * 4, 0.5, true);
    view.setInt8(header, -2);
  }
  return bytes;
}

test('Unicode boundaries and input limits match the Python contract', () => {
  assert.deepEqual(labels, [
    'O', 'B-street_address', 'I-street_address', 'B-locality', 'I-locality',
    'B-city', 'I-city', 'B-district', 'I-district', 'B-state', 'I-state',
    'B-postcode', 'I-postcode', 'B-country', 'I-country',
  ]);
  assert.deepEqual(tokenize('🏠 12 中'), [[0,2],[3,5],[6,7]]);
  assert.deepEqual(tokenize('a\u0085b\ufeffc'), [[0,1],[2,3],[3,4],[4,5]]);
  assert.equal(encode('a'.repeat(65)), null);
  assert.equal(encode(' '.repeat(513)), null);
  assert.equal(encode('x '.repeat(129)), null);
  assert.equal(encode('\ud800'), null);
  assert.equal(encode(' '), null);
  assert.equal(encode('a'.repeat(64)).width, 64);
  assert.equal(encode(' ' + 'a'.repeat(64), true).width, 65);
});

test('GPA3 float32 and int8 model binaries load to finite float weights', () => {
  const floatModel = readModel(modelBytes(0, 1));
  assert.equal(floatModel.weights.length, WEIGHT_COUNT);
  assert.equal(floatModel.weights[0], -1.25);
  assert.equal(floatModel.gapFeatures, true);

  const int8Model = readModel(modelBytes(1));
  assert.equal(int8Model.weights[0], -1);
  assert.equal(int8Model.gapFeatures, false);
  assert.equal(int8Model.transitions.length, 15 * 15);
  assert.equal(int8Model.start.length, 15);
  assert.equal(int8Model.end.length, 15);
});

test('GPA2 twenty-label artifacts are rejected explicitly', () => {
  assert.throws(() => readModel(modelBytes(0, 0, 'GPA2')), /GPA2.*GPA3 seven-label/);
});

test('invalid GPA3 binaries are rejected exactly', () => {
  assert.throws(() => readModel(new Uint8Array()), /Invalid gpu-postal model/);

  const gpa1 = modelBytes(0);
  gpa1[3] = 49;
  assert.throws(() => readModel(gpa1), /Invalid gpu-postal model/);

  for (const [offset, value] of [[4, 2], [8, 2], [12, 23], [16, 2]]) {
    const bytes = modelBytes(0);
    new DataView(bytes.buffer).setUint32(offset, value, true);
    assert.throws(() => readModel(bytes), /Invalid gpu-postal model/);
  }

  assert.throws(() => readModel(modelBytes(0).subarray(0, -1)), /Invalid gpu-postal model size/);
  const oversized = new Uint8Array(modelBytes(0).length + 1);
  oversized.set(modelBytes(0));
  assert.throws(() => readModel(oversized), /Invalid gpu-postal model size/);
  const nonfinite = modelBytes(0);
  new DataView(nonfinite.buffer).setFloat32(20, NaN, true);
  assert.throws(() => readModel(nonfinite), /Invalid gpu-postal model weights/);

  for (const scale of [0, -1, NaN, Infinity]) {
    const bytes = modelBytes(1);
    new DataView(bytes.buffer).setFloat32(20, scale, true);
    assert.throws(() => readModel(bytes), /Invalid gpu-postal model scale/);
  }
  const overflow = modelBytes(1);
  new DataView(overflow.buffer).setFloat32(20, 3e38, true);
  assert.throws(() => readModel(overflow), /Invalid gpu-postal model weights/);
});
