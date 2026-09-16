export const HIDDEN = 128;
export const LABEL_COUNT = 15;
export const MAX_TOKENS = 128;
export const MAX_WIDTH = 65;
const BYTE_CHANNELS = 32;

let cursor = 0;
const take = (size: number) => {
  const offset = cursor;
  cursor += size;
  return offset;
};

export const offsets = {
  embedding: take(257 * BYTE_CHANNELS),
  charConvWeight: take(BYTE_CHANNELS * BYTE_CHANNELS * 3),
  charConvBias: take(BYTE_CHANNELS),
  projectWeight: take(HIDDEN * BYTE_CHANNELS * 2),
  projectBias: take(HIDDEN),
  local: take(5 * HIDDEN),
  localBias: take(HIDDEN),
  gate1Weight: take(HIDDEN * HIDDEN),
  gate1Bias: take(HIDDEN),
  candidate1Weight: take(HIDDEN * HIDDEN),
  candidate1Bias: take(HIDDEN),
  combine1Weight: take(HIDDEN * HIDDEN * 2),
  combine1Bias: take(HIDDEN),
  gate2Weight: take(HIDDEN * HIDDEN),
  gate2Bias: take(HIDDEN),
  candidate2Weight: take(HIDDEN * HIDDEN),
  candidate2Bias: take(HIDDEN),
  combine2Weight: take(HIDDEN * HIDDEN * 2),
  combine2Bias: take(HIDDEN),
  outputWeight: take(LABEL_COUNT * HIDDEN),
  outputBias: take(LABEL_COUNT),
  transitions: take(LABEL_COUNT * LABEL_COUNT),
  start: take(LABEL_COUNT),
  end: take(LABEL_COUNT),
} as const;

export const WEIGHT_COUNT = cursor;
const sizes = [
  257 * BYTE_CHANNELS,
  BYTE_CHANNELS * BYTE_CHANNELS * 3,
  BYTE_CHANNELS,
  HIDDEN * BYTE_CHANNELS * 2,
  HIDDEN,
  5 * HIDDEN,
  HIDDEN,
  HIDDEN * HIDDEN,
  HIDDEN,
  HIDDEN * HIDDEN,
  HIDDEN,
  HIDDEN * HIDDEN * 2,
  HIDDEN,
  HIDDEN * HIDDEN,
  HIDDEN,
  HIDDEN * HIDDEN,
  HIDDEN,
  HIDDEN * HIDDEN * 2,
  HIDDEN,
  LABEL_COUNT * HIDDEN,
  LABEL_COUNT,
  LABEL_COUNT * LABEL_COUNT,
  LABEL_COUNT,
  LABEL_COUNT,
];

export interface Model {
  weights: Float32Array;
  transitions: Float32Array;
  start: Float32Array;
  end: Float32Array;
  gapFeatures: boolean;
}

export function readModel(bytes: Uint8Array): Model {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const magic = bytes.length >= 4 ? String.fromCharCode(...bytes.subarray(0, 4)) : '';
  if (magic === 'GPA2') {
    throw new TypeError('Unsupported gpu-postal GPA2 model; expected GPA3 seven-label model');
  }
  if (
    bytes.byteLength < 20 ||
    view.getUint8(0) !== 71 ||
    view.getUint8(1) !== 80 ||
    view.getUint8(2) !== 65 ||
    view.getUint8(3) !== 51 ||
    view.getUint32(4, true) !== 1 ||
    view.getUint32(8, true) > 1 ||
    view.getUint32(12, true) !== sizes.length ||
    view.getUint32(16, true) > 1
  ) {
    throw new TypeError('Invalid gpu-postal model');
  }
  const encoding = view.getUint32(8, true);
  const header = 20 + (encoding === 1 ? sizes.length * 4 : 0);
  const itemSize = encoding === 0 ? 4 : 1;
  if (bytes.byteLength !== header + WEIGHT_COUNT * itemSize) {
    throw new TypeError('Invalid gpu-postal model size');
  }
  const weights = new Float32Array(WEIGHT_COUNT);
  let position = 0;
  if (encoding === 0) {
    for (; position < WEIGHT_COUNT; position++) {
      weights[position] = view.getFloat32(header + position * 4, true);
    }
  } else {
    for (let tensor = 0; tensor < sizes.length; tensor++) {
      const scale = view.getFloat32(20 + tensor * 4, true);
      if (!Number.isFinite(scale) || scale <= 0) throw new TypeError('Invalid gpu-postal model scale');
      for (let i = 0; i < sizes[tensor]; i++, position++) {
        weights[position] = view.getInt8(header + position) * scale;
      }
    }
  }
  if (!weights.every(Number.isFinite)) throw new TypeError('Invalid gpu-postal model weights');
  return {
    weights,
    transitions: weights.slice(offsets.transitions, offsets.start),
    start: weights.slice(offsets.start, offsets.end),
    end: weights.slice(offsets.end),
    gapFeatures: view.getUint32(16, true) === 1,
  };
}

export async function loadModel(source: string | ArrayBuffer | Uint8Array): Promise<Model> {
  if (typeof source !== 'string') {
    return readModel(source instanceof Uint8Array ? source : new Uint8Array(source));
  }
  const response = await fetch(source);
  if (!response.ok) throw new Error(`Could not load model: ${response.status}`);
  return readModel(new Uint8Array(await response.arrayBuffer()));
}
