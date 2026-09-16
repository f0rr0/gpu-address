export type Offset = [number, number];
export interface Component { label: string; start: number; end: number; raw: string }

const fields = [
  'street_address', 'locality', 'city', 'district', 'state', 'postcode', 'country',
] as const;
export const labels = ['O', ...fields.flatMap(field => [`B-${field}`, `I-${field}`])];
const startAllowed = new Float32Array(labels.length);
const allowed = new Float32Array(labels.length * labels.length);
for (let next = 0; next < labels.length; next++) {
  const tag = labels[next];
  if (!tag.startsWith('I-')) continue;
  startAllowed[next] = -10000;
  for (let previous = 0; previous < labels.length; previous++) {
    if (labels[previous] !== `B-${tag.slice(2)}` && labels[previous] !== tag) {
      allowed[previous * labels.length + next] = -10000;
    }
  }
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

export function decode(
  emissions: number[][],
  transitions: Float32Array,
  starts: Float32Array,
  ends: Float32Array,
): number[] {
  let scores = Array.from(
    starts,
    (value, i) => Math.fround(Math.fround(value + startAllowed[i]) + emissions[0][i]),
  );
  const history: number[][] = [];
  for (let token = 1; token < emissions.length; token++) {
    const next = new Array(labels.length).fill(-Infinity);
    const previous = new Array<number>(labels.length);
    for (let target = 0; target < labels.length; target++) {
      for (let source = 0; source < labels.length; source++) {
        let score = Math.fround(scores[source] + transitions[source * labels.length + target]);
        score = Math.fround(score + allowed[source * labels.length + target]);
        score = Math.fround(score + emissions[token][target]);
        if (score > next[target]) { next[target] = score; previous[target] = source; }
      }
    }
    scores = next;
    history.push(previous);
  }
  let last = 0;
  for (let i = 1; i < labels.length; i++) {
    if (Math.fround(scores[i] + ends[i]) > Math.fround(scores[last] + ends[last])) last = i;
  }
  const result = [last];
  for (let token = history.length - 1; token >= 0; token--) {
    last = history[token][last];
    result.push(last);
  }
  return result.reverse();
}

export function encode(text: string, gapFeatures = false) {
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
    const prefix = gapFeatures ? (/[\r\n]/u.test(gap) ? [11] : gap ? [33] : []) : [];
    bytes.push([...prefix, ...Array.from(raw, byte => byte + 1)]);
  }
  const width = Math.max(...bytes.map(byte => byte.length));
  return { offsets, width, inputs: bytes.map(byte => byte.concat(Array(width - byte.length).fill(0))) };
}

export function components(path: number[], offsets: Offset[], text: string): Component[] {
  const result: Component[] = [];
  let previous = 'O';
  for (const [i, label] of path.entries()) {
    const tag = labels[label];
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
