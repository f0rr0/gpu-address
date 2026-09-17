import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, readFileSync } from 'node:fs';

// Freeze the selected export; packing must never silently select a newer run.
const bytes = readFileSync(new URL('model.bin', import.meta.url));
assert.equal(createHash('sha256').update(bytes).digest('hex'),
  '06a212f708a52c32e099c15e384e3bd149885c01d06c4b00343cc3b7ad894b60');
for (const name of ['README.md', 'LICENSE', 'MODEL_CARD.md', 'THIRD_PARTY_NOTICES.md']) {
  copyFileSync(new URL('../../' + name, import.meta.url), new URL(name, import.meta.url));
}
