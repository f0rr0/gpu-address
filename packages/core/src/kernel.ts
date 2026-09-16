import { HIDDEN, LABEL_COUNT, MAX_TOKENS, MAX_WIDTH, offsets } from './model.js';

export const shader = /* wgsl */ `
struct Parameters {
  tokens: u32,
  width: u32,
  padding0: u32,
  padding1: u32,
}

@group(0) @binding(0) var<storage, read> input: array<u32>;
@group(0) @binding(1) var<storage, read> weights: array<f32>;
@group(0) @binding(2) var<uniform> parameters: Parameters;
@group(0) @binding(3) var<storage, read_write> states: array<f32>;
@group(0) @binding(4) var<storage, read_write> emissions: array<f32>;

const HIDDEN: u32 = ${HIDDEN}u;
const BYTE_CHANNELS: u32 = 32u;
const LABELS: u32 = ${LABEL_COUNT}u;
const MAX_TOKENS: u32 = ${MAX_TOKENS}u;

fn read_state(stage: u32, token: u32, channel: u32) -> f32 {
  return states[(stage * MAX_TOKENS + token) * HIDDEN + channel];
}

fn write_state(stage: u32, token: u32, channel: u32, value: f32) {
  states[(stage * MAX_TOKENS + token) * HIDDEN + channel] = value;
}

@compute @workgroup_size(${HIDDEN})
fn classify(@builtin(local_invocation_id) local: vec3<u32>) {
  let h = local.x;

  if (h < BYTE_CHANNELS) {
    for (var token = 0u; token < parameters.tokens; token++) {
      var mean = 0.0;
      var maximum = -10000.0;
      var count = 0.0;
      for (var byte = 0u; byte < parameters.width; byte++) {
        let id = input[token * ${MAX_WIDTH}u + byte];
        if (id != 0u) {
          var ordered = weights[${offsets.charConvBias}u + h];
          for (var channel = 0u; channel < BYTE_CHANNELS; channel++) {
            for (var tap = 0u; tap < 3u; tap++) {
              let neighbor = i32(byte) + i32(tap) - 1;
              if (neighbor >= 0 && neighbor < i32(parameters.width)) {
                let neighbor_id = input[token * ${MAX_WIDTH}u + u32(neighbor)];
                if (neighbor_id != 0u) {
                  let weight = ${offsets.charConvWeight}u + (h * BYTE_CHANNELS + channel) * 3u + tap;
                  ordered += weights[${offsets.embedding}u + neighbor_id * BYTE_CHANNELS + channel] * weights[weight];
                }
              }
            }
          }
          let value = weights[${offsets.embedding}u + id * BYTE_CHANNELS + h] + max(ordered, 0.0);
          mean += value;
          maximum = max(maximum, value);
          count += 1.0;
        }
      }
      write_state(0u, token, h, mean / count);
      write_state(1u, token, h, maximum);
    }
  }
  storageBarrier();
  workgroupBarrier();

  for (var token = 0u; token < parameters.tokens; token++) {
    var value = weights[${offsets.projectBias}u + h];
    let row = ${offsets.projectWeight}u + h * BYTE_CHANNELS * 2u;
    for (var channel = 0u; channel < BYTE_CHANNELS; channel++) {
      value += read_state(0u, token, channel) * weights[row + channel];
      value += read_state(1u, token, channel) * weights[row + BYTE_CHANNELS + channel];
    }
    write_state(6u, token, h, tanh(value));
  }
  storageBarrier();
  workgroupBarrier();

  for (var token = 0u; token < parameters.tokens; token++) {
    var value = read_state(6u, token, h) + weights[${offsets.localBias}u + h];
    for (var tap = 0u; tap < 5u; tap++) {
      let neighbor = i32(token) + i32(tap) - 2;
      if (neighbor >= 0 && neighbor < i32(parameters.tokens)) {
        value += read_state(6u, u32(neighbor), h) * weights[${offsets.local}u + tap * HIDDEN + h];
      }
    }
    write_state(7u, token, h, tanh(value));
  }
  storageBarrier();
  workgroupBarrier();

  for (var layer = 0u; layer < 2u; layer++) {
    let input_stage = select(6u, 7u, layer == 0u);
    let output_stage = select(7u, 6u, layer == 0u);
    let gate_weight = select(${offsets.gate2Weight}u, ${offsets.gate1Weight}u, layer == 0u);
    let gate_bias = select(${offsets.gate2Bias}u, ${offsets.gate1Bias}u, layer == 0u);
    let candidate_weight = select(${offsets.candidate2Weight}u, ${offsets.candidate1Weight}u, layer == 0u);
    let candidate_bias = select(${offsets.candidate2Bias}u, ${offsets.candidate1Bias}u, layer == 0u);
    let combine_weight = select(${offsets.combine2Weight}u, ${offsets.combine1Weight}u, layer == 0u);
    let combine_bias = select(${offsets.combine2Bias}u, ${offsets.combine1Bias}u, layer == 0u);

    for (var token = 0u; token < parameters.tokens; token++) {
      var gate_value = weights[gate_bias + h];
      var candidate_value = weights[candidate_bias + h];
      for (var channel = 0u; channel < HIDDEN; channel++) {
        let item = read_state(input_stage, token, channel);
        gate_value += item * weights[gate_weight + h * HIDDEN + channel];
        candidate_value += item * weights[candidate_weight + h * HIDDEN + channel];
      }
      let gate = 1.0 / (1.0 + exp(-gate_value));
      let candidate = (1.0 - gate) * tanh(candidate_value);
      write_state(0u, token, h, gate);
      write_state(1u, token, h, candidate);
      write_state(2u, token, h, gate);
      write_state(3u, token, h, candidate);
      write_state(4u, token, h, gate);
      write_state(5u, token, h, candidate);
    }

    var stride = 1u;
    while (stride < parameters.tokens) {
      var forward = parameters.tokens;
      while (forward > stride) {
        forward -= 1u;
        let gate = read_state(2u, forward, h);
        write_state(3u, forward, h, read_state(3u, forward, h) + gate * read_state(3u, forward - stride, h));
        write_state(2u, forward, h, gate * read_state(2u, forward - stride, h));
      }
      var backward = 0u;
      while (backward + stride < parameters.tokens) {
        let gate = read_state(4u, backward, h);
        write_state(5u, backward, h, read_state(5u, backward, h) + gate * read_state(5u, backward + stride, h));
        write_state(4u, backward, h, gate * read_state(4u, backward + stride, h));
        backward += 1u;
      }
      stride *= 2u;
    }
    storageBarrier();
    workgroupBarrier();

    for (var token = 0u; token < parameters.tokens; token++) {
      var value = weights[combine_bias + h] + read_state(input_stage, token, h);
      let row = combine_weight + h * HIDDEN * 2u;
      for (var channel = 0u; channel < HIDDEN; channel++) {
        value += read_state(3u, token, channel) * weights[row + channel];
        value += read_state(5u, token, channel) * weights[row + HIDDEN + channel];
      }
      write_state(output_stage, token, h, tanh(value));
    }
    storageBarrier();
    workgroupBarrier();
  }

  for (var output = h; output < LABELS; output += HIDDEN) {
    for (var token = 0u; token < parameters.tokens; token++) {
      var value = weights[${offsets.outputBias}u + output];
      let row = ${offsets.outputWeight}u + output * HIDDEN;
      for (var channel = 0u; channel < HIDDEN; channel++) {
        value += read_state(7u, token, channel) * weights[row + channel];
      }
      emissions[token * LABELS + output] = value;
    }
  }
}
`;
