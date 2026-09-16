import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, readFileSync } from 'node:fs';

// Freeze the selected export; packing must never silently select a newer run.
const bytes = readFileSync(new URL('model.bin', import.meta.url));
assert.equal(createHash('sha256').update(bytes).digest('hex'),
  'e97cfb86c5ec703ad70ba684f2f373a44dc9c9e1018e517ab6799e74aa5ce84a');
for (const name of ['README.md', 'LICENSE', 'MODEL_CARD.md', 'THIRD_PARTY_NOTICES.md']) {
  copyFileSync(new URL('../../' + name, import.meta.url), new URL(name, import.meta.url));
}
