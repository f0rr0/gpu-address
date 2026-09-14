# GPU Lexer and GPU Time: implementation audit for the address-parser tooling decision

Inspected 2026-09-14. Repositories cloned read-only into scratch; findings below refer to exact commits, not floating README summaries. This is source inspection and selected unit-test execution, not independent retraining or browser benchmarking.

- GPU Lexer: `vercel-labs/gpu-lexer`, commit `1e514fd681e31d6b19296f985fb01d8fdc0ae74f`.
- GPU Time (the date/time project): `arikchakma/gpu-time`, commit `4c5058c55a72e38d129f490297777762ba618a33`.

## What frameworks they actually use

Both projects use ordinary PyTorch modules and custom training loops. Neither uses Lightning Trainer/Fabric, Accelerate, Hydra, MLflow, DVC, Hugging Face Trainer, or a distributed orchestration framework in the inspected training implementation. This is evidence that the workload fits plain PyTorch, not proof that a lifecycle framework cannot improve our project.

GPU Lexer is a pnpm monorepo. JavaScript owns corpus acquisition, Shiki supervision, feature extraction, training policy, Python process orchestration, evaluation and promotion. Python owns tensor computation. The Python dependency declaration is only `torch>=2.6,<3`; a custom setup script searches for Python, creates a venv and installs with pip. It does not have GPU Time's uv lock. [Requirements](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/requirements-torch.txt), [setup implementation](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/setup-torch.js), [orchestration](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/torch-runner.js).

GPU Time uses uv with a `pyproject.toml` requiring Python >=3.13,<3.14 and direct dependencies torch and numpy. Its checked-in lock resolves torch 2.14.0 and numpy 2.5.3. pnpm scripts invoke `uv run --project . python torch/...`. These are observed pins, not a tested recommendation to copy all versions into our project. [Project declaration](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/pyproject.toml), [lock](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/uv.lock), [commands](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/package.json).

Both separate `packages/core`, `packages/training`, `packages/benchmark`, and `apps/website`. The useful boundary is deployment/runtime versus research/training versus qualification. It is not necessary to copy every directory or make the Python project subordinate to pnpm. Our Python package can use `src/` packaging while a sibling web package owns deployment tests.

## Data and training: transferable implementation choices

**Memory representation matters more than adding a loader framework.** GPU Lexer stores sparse precomputed features in binary arrays and maps them with `torch.from_file`; record offsets select slices. Its batcher groups similar lengths and imposes a token budget, reducing padding. It benchmarks two candidate token budgets, warms up first, synchronizes MPS/CUDA around timings, and selects measured throughput. GPU Time instead reads precomputed binary arrays eagerly with `np.fromfile`; its sequence batches use 32/64/128 length buckets. Do not describe the latter as mmap or streaming. For our larger address corpus, Parquet can remain the auditable canonical dataset and bounded batches or a derived mmap cache can serve training. [Lexer loader and batching](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/torch/train.py#L110), [lexer throughput measurement](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/torch/train.py#L530), [Time loader](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/train.py#L25).

**Train with the deployment tokenizer.** GPU Time's TypeScript featurizer imports the exact tokenizer and label definitions from the core runtime. It streams JSONL into typed binary arrays, rejects unaligned supervision and unknown labels, records counts, skips unsupported sequence lengths explicitly, and saves structural fingerprints. Python trains those features rather than independently reimplementing the tokenizer. Our multilingual address parser especially needs equivalence for Unicode codepoints, UTF-16 offsets, normalization and token boundaries. Either share executable preprocessing or maintain a frozen cross-language conformance corpus; two similar-looking tokenizers are insufficient. [Featurizer](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/src/featurize.ts).

**Generated labels do not make a generated test independent.** GPU Time creates evaluation frames before training, excludes their fingerprints, refreshes generated training each epoch, and uses structural rather than just exact-string signatures. Its real-data assembler freezes an existing holdout, removes normalized gold texts, caps repeated repair phrases and filters contradictory labels. These are valuable defenses, but the annotations still need provenance and semantic review. For addresses, preserve physical/source identity and geographic groups before augmentation; broad country counts are not adequate split guarantees. [Training preparation](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/train.py#L190), [signature implementation](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/signature.py), [real split assembly](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/src/split-real.ts).

**Source weighting is experimental, not universally beneficial.** Time's real-data assembler records that oversampling small sources, capping dominant negative words, and mention substitution sometimes fixed one family while damaging others; those options are disabled by default. It also documents a recurrence blind spot in parser-agreement supervision. For us, libpostal confidence/agreement should not erase countries or address forms on which the teacher fails. This argues for source-stratified results and audited generated supervision before automatic reweighting. [Assembly implementation and measured comments](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/src/split-real.ts).

**Warm-start and resume are different.** Time saves optimizer state in checkpoints, but `--init` explicitly loads weights into a fresh optimizer; the inspected CLI has no exact-resume option. It records configuration, epoch, tokens seen, labels, source hashes and dataset hashes. This is useful provenance, but exact resumption additionally needs restoration of RNG, optimizer/scheduler state, batch ordering and regeneration state. A framework recommendation should be evaluated against that real gap rather than the mere existence of `.pt` files. [Training/checkpoint implementation](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/train.py).

## Browser delivery determines model design

Neither inspected deployed model uses ONNX Runtime or Wasm. Both ship specialized JavaScript/WebGPU inference and custom quantized weights. GPU Time has a JavaScript CPU implementation; GPU Lexer requires WebGPU. These projects demonstrate the package-size advantages and implementation burden of custom runtimes, not that such a rewrite is immediately justified for our ~615k-parameter GRU model.

GPU Time's network uses a small embedding, local depthwise convolution, bidirectional affine scans, global context and CRF transitions. The affine recurrence admits a parallel scan, unlike an arbitrary standard recurrent cell. It includes fake low-bit quantization and optional half-storage simulation during training. Its CRF reference explicitly reproduces JavaScript floating-point ordering and moves double-precision decode off MPS. This is a concrete warning that a nominally equivalent decoder or precision mode can change outputs. [Model implementation](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/model.py).

The Time exporter decodes the serialized quantized artifact back into its reference model, calibrates that artifact, builds the candidate package, compares end-to-end output, then publishes. This is stronger than testing float weights and assuming quantized inference will agree. Snapshot paths incorporate artifact and source hashes, protecting earlier evidence from overwrite. [Exporter](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/export.py#L703).

Time's automatic backend chooses GPU only when a batch has at least 32 jobs or 512 tokens. Smaller work stays on CPU; initialization is lazy, GPU failures can fall back in auto mode, and disposal/lifecycle are explicitly handled. The threshold is theirs, not a portable optimum. Our common single-address form input should measure cold and warm CPU/Wasm performance, initialization, worker overhead and cancellation as well as large-batch GPU throughput. [Runtime routing](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/core/src/tagger.ts#L121).

## Tests and release qualification

Time provides Python unittest files, TypeScript/Vitest tests, and real-browser Playwright parity code. The browser runner compares WebGPU to JavaScript CPU and stored PyTorch logits/decoded labels, checks UTF-16 token outputs, tests device-loss recovery, and compares the built package to source inference. The test uses Chromium with Chrome channel; this does not establish Safari qualification. [Browser harness](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/core/test/browser.ts).

The default Time CI installs JS dependencies, builds, runs core/benchmark tests, checks website types and npm contents, and enforces a compressed package-size gate. It does **not** install Python/run Python tests or execute its explicit GPU browser parity command. Lexer CI similarly omits the Python test suite and actual GPU browser qualification. The lesson is to put essential cross-language checks in CI, not simply copy the workflow. [Time CI](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/.github/workflows/ci.yml), [Lexer CI](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/.github/workflows/ci.yml).

GPU Time's current guard implementation checks support and corpus hashes, records fixed/broken examples, and uses an exact paired one-sided sign/McNemar calculation with a minimum-support policy. It can permit nonsignificant drops. This differs from a literal reading of prose saying every family must preserve its count. Repeated tuning on these gates is still development, and nonsignificance is not proof of noninferiority. For our project, keep a distinct final audit set and make acceptance margins, critical regressions and minimum sample support explicit. [Actual guard code](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/export.py#L189).

## Problems worth preserving as lessons

The Time model card records earlier evaluation using argmax despite a Viterbi production decoder; calibration also consumes a split named heldout, making it development data. It distinguishes committed parity reproducibility from full training reproducibility because ignored ancestral checkpoints and some historic data are unavailable. Its documentation also contains stale counts and contradictory status statements; use active JSON artifacts and executable code for precise claims. These are valuable cautions for our own report generation and release contracts. [Model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md).

Lexer provides a tracked compact active float/deployed checkpoint and pinned source manifest, so continuation from clean clone is more self-contained. Verification sources are repository/package-disjoint; Shiki-generated labels measure agreement with the chosen teacher mapping, not programming-language semantic truth. We should describe libpostal supervision with the same distinction. [Lexer active metadata](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/active/model-active.json), [source manifest](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/data/corpus.json), [label implementation](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/label.js).

## Concrete recommendation for our scope

Adopt the reproducibility and qualification contracts, not all bespoke infrastructure: uv lock, installable Python package, direct PyTorch model, bounded memory loading with length-aware batching, seeded data recipes, complete resume semantics, immutable run/artifact manifests, per-country/field/script diagnostics, independent annotated audit data, quantized deployed-decoder evaluation and actual browser parity/package budgets.

A thin Lightning Trainer or Fabric integration remains a reasonable option if it demonstrably replaces lifecycle code and preserves CRF/export behavior. These reference repositories supply no evidence that those frameworks themselves improve accuracy or throughput. Keep raw PyTorch as the comparison baseline; require an interruption/resume and fixed-batch parity test before migrating training.

No need to adopt a workflow service, distributed training, or multiple overlapping dataset stores for this single-machine experiment. Add these when recovery, remote compute, dataset size or collaboration imposes measured requirements. Runtime specialization is a separate experiment with an explicit whole-package byte target, not a prerequisite for reorganizing Python.

## Verification performed here

Read both live repository trees and the cited implementations. Ran GPU Time `test_model.py` using the existing Linux CPU scratch environment (Python 3.11 and PyTorch 2.14.0+cpu): 28 tests passed. This is not the repository's locked Python 3.13/numpy environment and not an M1/browser performance validation. No project dependencies, training code or runtime files were changed.

## Copyable comparison

| Concern | GPU Lexer | GPU Time | Address project implication |
|---|---|---|---|
| Training framework | Plain PyTorch; JS orchestration | Plain PyTorch; pnpm invokes uv | Trainer is a lifecycle choice, not required for this workload |
| Python environment | venv/pip; torch range | uv.lock; Python 3.13; torch/numpy | Use uv and platform-tested pins |
| Feature data | Binary arrays mapped by torch.from_file | Binary arrays loaded by np.fromfile | Audit in Parquet; batch or mmap training input when justified |
| Batching | Length buckets; synchronized token-budget benchmark | 32/64/128 buckets | Reduce padding and measure Mac throughput |
| Browser | Custom WebGPU | Custom JS CPU + WebGPU | Compare complete-package size and single-input latency |
| Experiment records | JSON, source/corpus metadata, active weights | JSON, checkpoint lineage, source/data hashes | Tracking services optional; immutable evidence required |
| Default CI gap | No Python test job or browser GPU run | No Python test job or browser GPU run | Add essential Python and deployed-output checks explicitly |

Commands executed in scratch:

```sh
/tmp/address-model-venv/bin/python -m unittest discover -s /tmp/research-gpu-time/packages/training/torch -p test_model.py
/tmp/address-model-venv/bin/python -m unittest discover -s /tmp/research-gpu-time/packages/training/torch -p test_decode.py
```

Decode test result: 9 tests run, 8 passed and 1 MPS-dependent test skipped on CPU. Model test result: 28 passed. Neither suite validates end-to-end training reproducibility or browser behavior.
