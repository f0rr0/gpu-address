# WebGPU pivot

The browser product now uses a fixed WebGPU model and no ONNX Runtime or Wasm.
This is an intentional replacement, not another selectable backend.

## Evidence

[GPU Lexer](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/architecture.md)
and [GPU Time](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md)
both co-design their learned recurrence and browser kernel. They use small
channel-wise affine state updates, custom WGSL and compact quantized weights.
They do not depend on a generic model runtime. GPU Time keeps a CPU path for
small automatic requests; GPU Lexer requires WebGPU.

The previous address model used two standard GRU operators. ONNX Runtime Web's
[current WebGPU operator table](https://github.com/microsoft/onnxruntime/blob/main/js/web/docs/webgpu-operators.md)
does not include GRU. Keeping that model would require CPU fallback, graph
decomposition or a custom GRU implementation.

## Address model

The replacement retains the existing Unicode tokenizer and BIO-constrained CRF:

1. 32-channel UTF-8 byte embeddings with a three-byte convolution, then mean/max pooling;
2. a five-token depthwise local mix;
3. two 128-channel bidirectional affine scans;
4. 41 field-label emissions;
5. TypeScript Viterbi decoding and span reconstruction.

The fixed architecture is `ordered-byte-conv32-scan128-v2` (159,308 parameters).
Padding embeddings are zero-initialized and masked before convolution. GPA2 has a
20-byte little-endian header: magic, architecture ID 1, encoding (0 float32 / 1 int8),
tensor count 24, and gap-feature flag. Float32 weights follow directly; int8 payloads
have 24 tensor scales followed by signed bytes. Export writes `model.f32.bin` for
qualification before the `model.bin` int8 candidate. GPA1 and ambiguous old Python
configs are rejected. The browser dequantizes int8 once,
uploads one f32 buffer and retains its device, pipeline and working buffers.
Each address uses one compute dispatch and one readback.

## Corrected ordered-model qualification

CPU and MPS tests pass for byte-width and token-padding invariance, including a
deliberately nonzero loaded padding row. Browser checks pass with gap features both
off and on, float32 before int8, comparing exact components and reconstructed BIO
paths on 12 fixtures per combination. These use fresh untrained weights: they
qualify the implementation, not address accuracy or trained-model quantization loss.
[Hash-bound qualification record](evidence/ordered-h128-v2-qualification-20260915.json)

## Historical unordered-model measurements

For the older 205,452-parameter model on the 10-core M1 Pro with 16 GB memory:

- PyTorch 2.14 selected MPS automatically. The 128-channel model trained 100,000
  rows in about 84 seconds per epoch at batch 512.
- A Chromium WebGPU run compiled and executed the shader, then matched Python
  paths and UTF-16 spans for 29 fixtures.
- The final run measured a 1.8 ms median warm parse over 100 calls. Setup varied
  from 23.7 to 369 ms across two uncontrolled browser/cache states, so cold setup
  is not yet characterized.
- The 168,001-byte Brotli model reached 84.12% exact on generated development
  data and 69.93% on the public development suite. Neither is independent gold.

The pivot deliberately omits CPU/Wasm fallback, dynamic architectures, operator
dispatch and runtime selection. Add one only after a supported-browser or
measured-workload requirement justifies the second implementation.
