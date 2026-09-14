# WebAssembly and WebGPU lessons for small parsers

## What the QIP comparison actually establishes

The linked page compares a hand-written JavaScript highlighter compiled to Wasm with gpu-lexer and other highlighters. It reports 265 ms for the Wasm implementation versus 533 ms for gpu-lexer on 5.56 MB of repeated minified JavaScript, on an M5 MacBook Air. Its module is about 12.7 kB. This is a different algorithm, not the same model on another backend.[^1]

Its four JavaScript fixtures achieve 99.95–100% agreement with a reduced Shiki label vocabulary. The page explicitly distinguishes that from multilingual evaluation. Outputs also differ: HTML, source ranges, tokens, and syntax trees. The headline includes different output-allocation work.[^1]

These are author-reported measurements, not reproduced results. They support including compact deterministic implementations in our experiments. They do not establish that Wasm beats neural inference generally, or that our M1 Pro will reproduce the timings.

## The repository contains a separate neural SIMD experiment

QIP also implements the shape of gpu-lexer's final neural classifier in Zig, Odin, and relaxed-SIMD WAT. It uses synthetic weights/features and an approximate activation, not a verified complete model port. The workload is 2,483,870 tokens; reported means are:[^2]

| Kernel | Time | Wasm binary, excluding weights |
| --- | ---: | ---: |
| Zig SIMD | 3,380 ms | 4.38 kB |
| Odin SIMD | 2,862 ms | 2.69 kB |
| Relaxed-SIMD WAT | 3,152 ms | 2.62 kB |

The fastest classifier alone exceeded the complete 533 ms WebGPU run. This is a single-core, high-volume prototype, not an optimized CPU upper-performance bound. The binary sizes omit weights; 41,321 float32 weights would occupy 165,284 bytes before compression. The experiment establishes neither trained-label parity nor small-input latency.[^2]

The benchmark code seeds synthetic buffers, checks scalar/SIMD labels, alternates timing order, and checks stable checksums. The variant runner additionally compares labels across implementations. These checks establish consistency within that synthetic experiment, not agreement with the deployed gpu-lexer model.[^3]

**Implication for the phone/address experiments:** algorithm choice and execution backend are separate variables. A tiny rule-based Wasm parser can outperform a learned pipeline, while a neural model's large-batch arithmetic can favor WebGPU. Short phone/address inputs require their own measurements.

## 1. Keep the comparison factorial

There are two separate research questions:

1. Does a compact model improve the size/quality tradeoff against an equally capable deterministic or statistical baseline?
2. For a fixed model and output contract, which backend provides the best latency, throughput, startup and memory behavior?

Do not compare a region-scoped Wasm phone parser with a globally capable neural parser and attribute the entire difference to Wasm. Likewise, do not compare a parser returning component spans with another doing normalization, formatting, and object construction without exposing the difference.

Proposed backend matrix:

| Backend | Purpose | What must be measured |
| --- | --- | --- |
| Plain JavaScript | Simplest browser reference and potential shipping implementation | Actual typed-array/decoder cost and complete bundle |
| Wasm scalar | Portable CPU model or deterministic parser | Compilation, input/output copies, runtime memory |
| Wasm SIMD | Vectorized version of the same model | Useful work per short sequence; float/quantization parity |
| WebGPU | Batched model inference | Device/pipeline startup, dispatch, synchronization and readback |

Start with JS plus one straightforward Wasm path. SIMD, threads, and custom shader work should be justified by profiles, not added simultaneously. Training with MPS on a Mac does not require deploying with WebGPU.

## 2. Measure the public result, then its stages

For each backend, use the same input strings and the same final result schema. When studying inference itself, also hold weights, tokenization, features, normalization, decoder, and region metadata constant.

Record the following stages separately:

```text
fetch/decompress
compile or create inference session
first invocation
UTF-8 encoding and offset mapping
tokenization/features
input transfer or memory copy
model inference
output readback
sequence decoding
canonicalization/component grouping
public-result construction
```

Report total wall time as well. Faster matrix multiplication is irrelevant if feature extraction or CRF decoding dominates the actual phone/address call. A Wasm worker can keep the UI responsive without making inference faster; include its message/copy overhead in application timing.

For WebGPU, await the operation that makes the required result available. Timing only command submission measures scheduling, not completion. For Wasm, include copies required by the real ABI. Reuse initialized instances for warm measurements and measure initialization separately.

Do not force both engines through an artificial adapter that favors one representation. An additional shared-JSON benchmark is useful for consumers, while native stage timings explain allocation differences.

## 3. Use representative workloads

The QIP workload is useful for sustained throughput, but it is unlike parsing one form field. Proposed workloads for these experiments are:

| Workload | Why it matters |
| --- | --- |
| One short phone candidate | Normal interactive parsing; startup/dispatch may dominate |
| One short address | Ordinary field parsing, including non-Latin text |
| Short contact fragment with numeric clutter | Extraction and negative discrimination |
| Mixed batches of 8, 32, 128 and 1,024 records | Locate the actual CPU/GPU crossover |
| Longer supported text, up to an explicit limit | Bound memory and avoid silent truncation |
| Mostly negative and ambiguous inputs | Avoid timing only easy positives |

Report lengths in bytes, Unicode code points where relevant, and actual model tokens. “One thousand addresses” is not a stable workload if token lengths or scripts differ.

Alternate backend order, run without competing heavy jobs, retain individual samples, and report medians and tail latency. For very short calls, time blocks of varying inputs to overcome timer resolution, while preserving per-call overhead. Avoid drawing p95 conclusions from three runs.

Use the M1 Pro/16 GB as the primary development measurement, with browser/version, OS, power state, model/data hashes, and threading recorded. Check Safari and Chromium separately. A faster machine can be additional evidence but should not replace the target-device result.

## 4. Count the whole deployable artifact

Maintain separate byte counts for weights, JS glue, Wasm/shaders, tokenizer tables, metadata/gazetteers, and other runtime assets. Report raw, gzip and Brotli sizes consistently, plus total assets fetched before the first usable result. A preinstalled/shared runtime can be shown as an incremental-size scenario, but not as the only size figure.

Record runtime-resident memory separately: packed download weights may expand to float32, temporary tensors need space, and browser engines retain their own compiled code/resources. Wasm linear-memory capacity is not total process memory; GPU buffers and JS heap should not disappear from the comparison.

For phone parsing, a compressed model plus unchanged global numbering metadata may be larger than a scoped deterministic library. For addresses, compact weights plus a large locality dictionary may not solve the original browser-download problem. Both are legitimate experimental outcomes.

## 5. Treat numerical parity as an explicit test

A real model port must share the trained weights, feature hashing, tensor layout, activation semantics, quantization scales and decoding rules. A synthetic checksum cannot establish those properties.

Use a staged parity corpus:

1. Known feature vectors: check preprocessing byte-for-byte.
2. Fixed real inputs: compare float32 intermediate tensors within declared tolerances.
3. Near-tie cases: compare chosen labels and sequence paths, with deterministic tie-breaking.
4. Quantized model: compare exact public outputs and identify new failures.
5. Cross-browser packaged build: rerun source spans, leading zeros, Unicode and abstention fixtures.

SIMD reduction order, relaxed fused operations and half-precision intermediates can change close decisions. Bit-identical internal floats may be unnecessary, but observable output differences must be counted rather than hidden under an average tensor tolerance.

Store offsets internally under a declared encoding. A Wasm model commonly consumes UTF-8 bytes while browser string slicing uses UTF-16 code units. Preserve a conversion map; test supplementary characters before, inside and after mentions. Never silently return byte offsets as JavaScript offsets.

For a small custom ABI, use bounded input/output buffers, validate returned lengths and status, and reject over-capacity inputs explicitly. Do not assume a Wasm sample wrapper is a production error-handling contract. JSON escaping and output serialization remain ordinary code.

## 6. Generic inference runtime versus a dedicated kernel

ONNX Runtime Web provides a Wasm CPU path and a WebGPU path. Its documentation identifies Wasm as suitable for very small models, describes the cost of transfers and CPU/GPU placement, and exposes threading and worker controls.[^4]

Use a generic runtime for an early export/correctness baseline if the model's operators are supported. Measure its complete delivered assets before choosing it for a tens-of-kilobytes product. A dedicated C/Rust/Zig Wasm kernel may reduce deployment overhead for a small fixed architecture, but it adds numerical and maintenance obligations; it should follow a useful trained candidate.

Standard SIMD, relaxed SIMD and threads are separate capabilities. Detect the capabilities actually used and retain a tested fallback. ONNX's Wasm multithreading requires cross-origin isolation; do not make extra deployment headers mandatory merely to accelerate single short records. Single-threaded SIMD is a separate option. Its proxy worker improves responsiveness rather than inference speed, and proxy mode has WebGPU-specific limitations.[^4][^5]

gpu-time's inspected architecture already chooses CPU for small inputs and switches to WebGPU at a documented batch/token threshold. That threshold is evidence that a mixed policy can work, not a threshold to copy into phone/address code.[^6]

## 7. Two layers of correctness checks

QIP combines broad differential comparisons with small executable fixtures. The broad comparisons locate disagreement patterns; reduced fixtures make understood behavior cheap to recheck.[^1][^3]

Apply the same structure here:

- **Broad audit:** frozen generated and real-input corpora; compare teacher, baseline, candidate and deployed artifact. Produce exact-output metrics, per-field/per-country results and disagreement clusters.
- **Fast fixtures:** minimal cases for each understood failure—significant phone zeros, extension attachment, numeric negatives, apartment boundaries, rare field labels, Unicode offsets, and ambiguity policies.

A minimized fixture is a regression contract after it has influenced development. It is not independent accuracy evidence. Keep a locked evaluation corpus outside the cycle that generates fixes.

Record whether expected output reflects teacher compatibility or an intentionally different product contract. If the teacher interprets an order ID as a phone number, preserving that behavior and rejecting it semantically are different objectives. QIP's oracle-driven workflow is useful precisely when the expected contract is explicit.

## 8. Recommended experimental order

Follow the [current experiment plan](phone-postal-experiments.md): audit data, train a functioning reference, and export it to a minimal browser harness early. Verify exportability, results and total runtime cost before a long training campaign. Then refine accuracy, compress, and qualify the selected package. WebGPU is a later measured option if CPU latency or batch throughput justifies it.

The broader backend matrix above is a research reference, not a requirement to implement every combination. The final choice should be supported by accuracy, coverage, complete bytes, cold latency, warm single-input latency, batch throughput and memory on the target device.

## Sources

Inspected September 14, 2026. The linked page was read in full, and the repository benchmark scripts and classifier implementation were inspected. Published measurements were not rerun. QIP repository snapshot: `ac753990551a76d5e5c8b831019eebc78095e530`.

[^1]: QIP. [Syntax highlight comparison](https://qip.dev/syntax-highlight-comparison), including capability/output distinctions and executable-oracle workflow. [Pinned page source](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/site/syntax-highlight-comparison.md).
[^2]: QIP. [Benchmark README: WebAssembly SIMD experiment](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/benchmarks/syntax-highlight-comparison/README.md).
[^3]: QIP. [SIMD benchmark script](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/benchmarks/syntax-highlight-comparison/benchmark-gpu-lexer-wasm-simd.mjs), [variant comparison](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/benchmarks/syntax-highlight-comparison/benchmark-gpu-lexer-wasm-variants.mjs), and [Zig classifier implementation](https://github.com/patrickgwsmith/qip/blob/ac753990551a76d5e5c8b831019eebc78095e530/benchmarks/syntax-highlight-comparison/gpu-lexer-classifier-simd.zig).
[^4]: ONNX Runtime. [Web performance diagnosis](https://onnxruntime.ai/docs/tutorials/web/performance-diagnosis.html).
[^5]: ONNX Runtime. [Environment flags and session options](https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html) and [Web builds](https://onnxruntime.ai/docs/build/web.html).
[^6]: gpu-time. [Architecture: CPU/WebGPU dispatch and shared decoding](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md).
