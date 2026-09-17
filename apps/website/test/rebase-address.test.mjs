import assert from "node:assert/strict";
import { rebaseAddress } from "../lib/rebase-address.ts";

const source = "123 Main St, Boston";
const result = {
  status: "unassessed",
  offsetEncoding: "utf-16",
  components: [
    { label: "street_address", raw: "123 Main St", start: 0, end: 11 },
    { label: "city", raw: "Boston", start: 13, end: 19 },
  ],
};
const fixture = { ...result, components: [...result.components] };
for (const next of [
  "123 Main Street, Boston",
  "123 Main St, Bost",
  "🧭 123 Main St, Boston",
]) {
  const rebased = rebaseAddress(fixture, source, next);
  assert.equal(rebased.components.length, 2);
  for (const part of rebased.components) {
    assert.equal(part.raw, next.slice(part.start, part.end));
    assert.ok(part.start >= 0 && part.end <= next.length);
  }
}
assert.equal(rebaseAddress(fixture, source, ""), null);
assert.equal(rebaseAddress(fixture, source, "London")?.components.length, 0);
assert.deepEqual(rebaseAddress(fixture, source, source), fixture);
console.log("Address highlight rebasing passed");
