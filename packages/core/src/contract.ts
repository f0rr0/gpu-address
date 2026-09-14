export type Offset = [number, number];
export interface Component { label: string; start: number; end: number; raw: string }
export interface Decoder {
  labels: string[];
  transitions: number[][];
  allowed: number[][];
  start: number[];
  end: number[];
  start_allowed: number[];
  gap_features: boolean;
}

export function tokenize(text: string): Offset[] {
  const offsets: Offset[] = [];
  let start: number | null = null;
  let offset = 0;
  for (const char of text) {
    const cjk = (char >= '\u3400' && char <= '\u9fff') || (char >= '\uf900' && char <= '\ufaff');
    const word = /[\p{L}\p{N}\p{M}]/u.test(char) && !cjk;
    if (!word && start !== null) { offsets.push([start, offset]); start = null; }
    if (word && start === null) start = offset;
    else if (!word && !/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u.test(char)) offsets.push([offset, offset + char.length]);
    offset += char.length;
  }
  if (start !== null) offsets.push([start, offset]);
  return offsets;
}

export function decode(emissions: number[][], decoder: Decoder): number[] {
  const labels = decoder.labels.length;
  let scores = decoder.start.map((value, i) => value + decoder.start_allowed[i] + emissions[0][i]);
  const history: number[][] = [];
  for (let t = 1; t < emissions.length; t++) {
    const next = new Array(labels).fill(-Infinity);
    const previous = new Array(labels);
    for (let j = 0; j < labels; j++) {
      for (let i = 0; i < labels; i++) {
        const score = scores[i] + decoder.transitions[i][j] + decoder.allowed[i][j] + emissions[t][j];
        if (score > next[j]) { next[j] = score; previous[j] = i; }
      }
    }
    scores = next;
    history.push(previous);
  }
  let last = 0;
  for (let i = 1; i < labels; i++) if (scores[i] + decoder.end[i] > scores[last] + decoder.end[last]) last = i;
  const result = [last];
  for (let t = history.length - 1; t >= 0; t--) { last = history[t][last]; result.push(last); }
  return result.reverse();
}


export function encode(text: string, decoder: Decoder) {
  if (typeof text !== 'string') throw new TypeError('Expected an address string');
  if (Array.from(text).length > 512 || /[\uD800-\uDFFF]/u.test(text)) return null;
  const offsets = tokenize(text);
  if (!offsets.length || offsets.length > 128) return null;
  const encoder = new TextEncoder();
  const bytes: number[][] = [];
  for (const [i, [start, end]] of offsets.entries()) {
    const raw = encoder.encode(text.slice(start, end));
    if (raw.length > 64) return null;
    const gap = text.slice(i ? offsets[i - 1][1] : 0, start);
    const prefix = decoder.gap_features ? (/[\r\n]/u.test(gap) ? [11] : gap ? [33] : []) : [];
    bytes.push([...prefix, ...Array.from(raw, b => b + 1)]);
  }
  const width = Math.max(...bytes.map(b => b.length));
  return { offsets, width, inputs: bytes.map(b => b.concat(Array(width - b.length).fill(0))) };
}

export function components(path: number[], offsets: Offset[], text: string, decoder: Decoder): Component[] {
  const result: Component[] = [];
  let previous = 'O';
  for (const [i, label] of path.entries()) {
    const tag = decoder.labels[label];
    if (tag !== 'O') {
      const [start, end] = offsets[i];
      const field = tag.slice(2);
      if (tag.startsWith('I-') && (previous === `B-${field}` || previous === `I-${field}`)) {
        const last = result[result.length - 1];
        last.end = end;
        last.raw = text.slice(last.start, end);
      } else result.push({ label: field, start, end, raw: text.slice(start, end) });
    }
    previous = tag;
  }
  return result;
}

export function validateDecoder(value: unknown): asserts value is Decoder {
  if (!value || typeof value !== 'object') throw new TypeError('Invalid decoder');
  const d = value as Decoder;
  if (!Array.isArray(d.labels) || d.labels.length !== 41 || d.labels[0] !== 'O' ||
      new Set(d.labels).size !== 41 || d.labels.some(x => typeof x !== 'string') ||
      typeof d.gap_features !== 'boolean') throw new TypeError('Invalid decoder labels or configuration');
  const vector = (v: unknown): boolean => Array.isArray(v) && v.length === d.labels.length && v.every(x => typeof x === 'number' && Number.isFinite(x));
  if (![d.start, d.end, d.start_allowed].every(vector) ||
      ![d.transitions, d.allowed].every(m => Array.isArray(m) && m.length === d.labels.length && m.every(vector))) {
    throw new TypeError('Invalid decoder dimensions or weights');
  }
}
