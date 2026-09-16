import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, readFileSync } from 'node:fs';

// Freeze the selected export; packing must never silently select a newer run.
const bytes = readFileSync(new URL('model.bin', import.meta.url));
assert.equal(createHash('sha256').update(bytes).digest('hex'),
  '4ca878842b0eef37037f9ca5fa8f77096b54bb5ff34c42d4c3927d99b7a65624');
for (const name of ['LICENSE', 'MODEL_CARD.md', 'THIRD_PARTY_NOTICES.md']) {
  copyFileSync(new URL('../../' + name, import.meta.url), new URL(name, import.meta.url));
}
