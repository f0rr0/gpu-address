import assert from 'node:assert/strict';
import { test } from 'node:test';
import { encode, tokenize, validateDecoder } from '../dist/contract.js';

test('Unicode boundaries and input limits match the Python contract', () => {
  const d = { gap_features: false };
  assert.deepEqual(tokenize('🏠 12 中'), [[0,2],[3,5],[6,7]]);
  assert.deepEqual(tokenize('a\u0085b\ufeffc'), [[0,1],[2,3],[3,4],[4,5]]);
  assert.equal(encode('a'.repeat(65), d), null);
  assert.equal(encode(' '.repeat(513), d), null);
  assert.equal(encode('x '.repeat(129), d), null);
  assert.equal(encode('\ud800', d), null);
  assert.equal(encode(' ', d), null);
  assert.equal(encode('a'.repeat(64), d).width, 64);
  assert.equal(encode(' ' + 'a'.repeat(64), {gap_features:true}).width, 65);
  assert.throws(() => validateDecoder({}), /Invalid decoder/);
});
