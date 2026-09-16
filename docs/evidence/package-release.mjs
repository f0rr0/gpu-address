// Run after npm pack --workspace packages/core. No publishing or training.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { brotliCompressSync, gzipSync } from 'node:zlib';

const root = resolve(import.meta.dirname, '../..');
const out = resolve(root, 'dist/release');
const run = 'runs/ordered-h128-english-seven-20260916';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const read = path => readFileSync(resolve(root, path));
const pkg = JSON.parse(read('packages/core/package.json'));
const archive = `${pkg.name}-${pkg.version}.tgz`;
const data = JSON.parse(read('data/english-seven-20260916/manifest.json'));
assert.equal(sha(read('packages/core/model.bin')),
  '4ca878842b0eef37037f9ca5fa8f77096b54bb5ff34c42d4c3927d99b7a65624');
assert.equal(sha(read(run + '/best.pt')),
  '436dc0a84fca3816a851f28a5eb56d716153acc993748ddc16768e7c6502e7ec');
mkdirSync(out, {recursive:true});
const files = {
  [archive]:archive,
  'model.bin':'packages/core/model.bin',
  'epoch-12.pt':run + '/best.pt',
  'MODEL_CARD.md':'MODEL_CARD.md',
  'LICENSE':'LICENSE',
  'THIRD_PARTY_NOTICES.md':'THIRD_PARTY_NOTICES.md',
  'browser-qualification.json':'docs/evidence/release-qualification-20260917.json',
};
const assets = {};
for (const [name, path] of Object.entries(files)) {
  const bytes = read(path);
  assets[name] = {bytes:bytes.length,sha256:sha(bytes)};
  copyFileSync(resolve(root,path),resolve(out,name));
}
const runtime = {};
for (const name of ['index.js','contract.js','kernel.js','model.js']) {
  const bytes = read('packages/core/dist/' + name);
  runtime[name] = {bytes:bytes.length,sha256:sha(bytes)};
}
const payloads = [...Object.keys(runtime).map(n => read('packages/core/dist/' + n)), read('packages/core/model.bin')];
const manifest = {
  name:pkg.name,version:pkg.version,epoch:12,format:'GPA3 int8 storage / float32 GPU arithmetic',
  assets,runtime,
  payload:{rawBytes:payloads.reduce((n,b)=>n+b.length,0),
    gzipBytes:payloads.reduce((n,b)=>n+gzipSync(b).length,0),
    brotliBytes:payloads.reduce((n,b)=>n+brotliCompressSync(b).length,0),
    note:'Compressed sizes are local per-file calculations, not measured CDN transfer. Includes four JS modules and weights only.'},
  data:{countries:data.countries,trainingRows:3790046,source_counts:data.source_counts,
    inputs:Object.fromEntries(Object.entries(data.inputs).map(([p,s])=>[p.startsWith('/')?relative(root,p):p,s])),
    outputs:data.outputs,split_policy:data.split_policy,limitations:data.limitations},
  licenses:'Original code/documentation MIT; model source conditions preserved in THIRD_PARTY_NOTICES.md',
};
const text = JSON.stringify(manifest,null,2)+'\n';
writeFileSync(resolve(out,'release-manifest.json'),text);
writeFileSync(resolve(root,'docs/evidence/release-package-20260917.json'),text);
writeFileSync(resolve(out,'SHA256SUMS'),[
  ...Object.entries(assets).map(([name,a])=>`${a.sha256}  ${name}`),
  `${sha(Buffer.from(text))}  release-manifest.json`,
].join('\n')+'\n');
console.log(JSON.stringify({out,archive:assets[archive],payload:manifest.payload},null,2));
