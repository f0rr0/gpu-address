/// <reference types="@webgpu/types" />

import { components, decode, encode, type Component } from './contract.js';
import { shader } from './kernel.js';
import { HIDDEN, LABEL_COUNT, loadModel, MAX_TOKENS, MAX_WIDTH } from './model.js';
export type { Component } from './contract.js';

export interface ParseResult {
  status: 'unassessed' | 'unsupported';
  components: Component[];
  offsetEncoding: 'utf-16';
}

export async function createParser(
  source: string | ArrayBuffer | Uint8Array = new URL('../model.bin', import.meta.url).href,
) {
  if (typeof navigator === 'undefined' || !navigator.gpu) throw new Error('WebGPU is unavailable');
  const model = await loadModel(source);
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) throw new Error('WebGPU adapter is unavailable');
  const device = await adapter.requestDevice();
  const module = device.createShaderModule({ code: shader });
  const errors = (await module.getCompilationInfo()).messages.filter(message => message.type === 'error');
  if (errors.length) throw new Error(errors.map(error => error.message).join('\n'));
  const pipeline = await device.createComputePipelineAsync({
    layout: 'auto',
    compute: { module, entryPoint: 'classify' },
  });
  const makeBuffer = (size: number, usage: GPUBufferUsageFlags) =>
    device.createBuffer({ size, usage });
  const weights = makeBuffer(model.weights.byteLength, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST);
  const input = makeBuffer(MAX_TOKENS * MAX_WIDTH * 4, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST);
  const parameters = makeBuffer(16, GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST);
  const states = makeBuffer(8 * MAX_TOKENS * HIDDEN * 4, GPUBufferUsage.STORAGE);
  const output = makeBuffer(MAX_TOKENS * LABEL_COUNT * 4, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC);
  const readback = makeBuffer(MAX_TOKENS * LABEL_COUNT * 4, GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST);
  device.queue.writeBuffer(weights, 0, model.weights);
  const bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: input } },
      { binding: 1, resource: { buffer: weights } },
      { binding: 2, resource: { buffer: parameters } },
      { binding: 3, resource: { buffer: states } },
      { binding: 4, resource: { buffer: output } },
    ],
  });
  let closed = false;
  let pending: Promise<void> = Promise.resolve();

  const infer = async (text: string): Promise<ParseResult> => {
    const encoded = encode(text, model.gapFeatures);
    if (!encoded) return { status: 'unsupported', components: [], offsetEncoding: 'utf-16' };
    const values = new Uint32Array(MAX_TOKENS * MAX_WIDTH);
    for (let token = 0; token < encoded.inputs.length; token++) {
      values.set(encoded.inputs[token], token * MAX_WIDTH);
    }
    device.queue.writeBuffer(input, 0, values);
    device.queue.writeBuffer(
      parameters,
      0,
      new Uint32Array([encoded.inputs.length, encoded.width, 0, 0]),
    );
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(pipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(1);
    pass.end();
    const byteLength = encoded.inputs.length * LABEL_COUNT * 4;
    encoder.copyBufferToBuffer(output, 0, readback, 0, byteLength);
    device.queue.submit([encoder.finish()]);
    await readback.mapAsync(GPUMapMode.READ, 0, byteLength);
    const flat = new Float32Array(readback.getMappedRange(0, byteLength).slice(0));
    readback.unmap();
    if (!Array.from(flat).every(Number.isFinite)) throw new Error('Non-finite model output');
    const emissions = encoded.inputs.map((_, token) =>
      Array.from(flat.slice(token * LABEL_COUNT, (token + 1) * LABEL_COUNT)),
    );
    const path = decode(emissions, model.transitions, model.start, model.end);
    return {
      status: 'unassessed',
      components: components(path, encoded.offsets, text),
      offsetEncoding: 'utf-16',
    };
  };

  return {
    parse(text: string): Promise<ParseResult> {
      if (closed) throw new Error('Parser has been disposed');
      const result = pending.then(() => infer(text));
      pending = result.then(() => undefined, () => undefined);
      return result;
    },
    async dispose() {
      if (closed) return;
      closed = true;
      await pending;
      for (const buffer of [weights, input, parameters, states, output, readback]) buffer.destroy();
      device.destroy();
    },
  };
}
