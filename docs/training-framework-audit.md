# Training framework review for the browser address parser

Research date: 2026-09-14. Primary-source documentation, upstream source inspection, and a bounded local graph-capture probe. No project code or environments were changed.

## Decision

**Use plain PyTorch as the core and keep the existing explicit training loop for the first packaged version.** PyTorch is already a proper training framework; professionalism comes from repeatable data, resumed-state correctness, readable boundaries, reliable evaluation and tested exports. A framework migration is not an accuracy intervention.

The earlier Lightning-first recommendation was too categorical. Lightning Trainer is a credible convenience choice, but there is no measured evidence that it improves this model's throughput, accuracy, memory, or browser export. Fabric is the first optional layer to add when device launching, precision or distributed concerns become repetitive. Use one loop-management option, never Fabric plus Accelerate plus Trainer.

This recommendation is an engineering judgment for the existing 615,244-parameter model, its short single-machine runs, and the already-working custom CRF/export code. It is not a general claim that handwritten loops outperform Trainer.

## Comparison for our actual workload

| Choice | What it buys | Cost or limitation here | Decision |
|---|---|---|---|
| Plain PyTorch | Exact control of byte encoder, packed biGRU, CRF objective and evaluation; no model rewrite | We own checkpoint/resume correctness and training lifecycle tests | Default now |
| Lightning Fabric | Device/strategy handling, precision, backward, explicit save/load while keeping the loop | Does not choose data splits, restore every custom cursor automatically, or remove custom loop ownership | First optional training adapter |
| Lightning Trainer | Standard fit/validate lifecycle, automatic optimization, callbacks, logging and checkpoint integration | Need a LightningModule adapter and migration parity checks; defaults can add validation/logging work | Good if the project grows several experiments that share substantial lifecycle logic |
| Hugging Face Accelerate | Similar explicit-loop approach, launchers, wrappers, mixed precision, checkpoint APIs; stateful loader integration | More useful when adopting the HF training ecosystem or multiple accelerators; no browser-specific benefit | Alternative to Fabric, not an additional dependency |
| MLX | Apple-oriented array framework, lazy evaluation, compilation, GRU and neural-network primitives | Would rewrite model/loss and validate optimizer, masking, GRU equations and export; no demonstrated speedup on our M1 Pro | Separate benchmark only if actual Mac profiling justifies a port |
| Keras 3 | High-level training and multiple backends; ONNX export exists | Rewrite/adapt custom packed recurrence and CRF; backend portability does not prove export operator compatibility | No migration case for this existing PyTorch model |
| JAX/Flax | Functional transformations and compilation attractive for new research | Rewrite and new export path; Apple's JAX Metal plugin still explicitly experimental | Do not choose as this project's default |

Fabric's documented interface leaves training under user control and can unwrap model/optimizer state for checkpoints. Its save/load API does not decide what application state belongs in a checkpoint. [Fabric guide](https://lightning.ai/docs/fabric/stable/guide/), [checkpoint API](https://api.lightning.ai/docs/fabric/stable/guide/checkpoint/checkpoint.html).

Accelerate wraps existing PyTorch objects, provides launch/backward/precision and state save/load, and can include a stateful data loader when configured. Its MPS documentation explicitly states that it integrates the PyTorch backend, rather than fixing backend problems. [Migration guide](https://huggingface.co/docs/accelerate/basic_tutorials/migration), [MPS support](https://huggingface.co/docs/accelerate/usage_guides/mps).

Lightning's source includes a `barebones` mode that disables checkpointing, logging, progress bars, summaries and sanity validation for raw-overhead comparisons. This is useful evidence that meaningful benchmarking must equalize features, not a measured claim of unacceptable overhead. Compare both normal matched-feature runs and stripped-loop timings. [Pinned Trainer source](https://github.com/Lightning-AI/pytorch-lightning/blob/0a6021195378fc3803db141bfc2aaa734615493e/src/lightning/pytorch/trainer/trainer.py), [checkpoint guide](https://github.com/Lightning-AI/pytorch-lightning/blob/master/docs/source-pytorch/common/checkpointing_basic.rst).

MLX's official export guide serializes functions for execution in another **MLX frontend**, such as C++; that is not an ONNX/browser export guarantee. MLX may still train weights consumed by a custom runtime, but doing so creates a separate conversion and numerical-parity obligation. Its currently served documentation identifies version 0.32.2. [MLX documentation](https://ml-explore.github.io/mlx/build/html/index.html), [pinned export guide](https://github.com/ml-explore/mlx/blob/3dc6e9b57e0b89c98949cec2f31468408b4edbda/docs/src/usage/export.rst).

Keras currently documents ONNX export from TensorFlow, JAX and Torch backends, so dismissing it as unable to export would be wrong. However its export API does not establish support for our exact custom model. Apple's JAX Metal page still calls the plugin experimental and states that it does not pass all upstream tests. [Keras export](https://keras.io/api/models/model_saving_apis/export/), [Apple JAX Metal](https://developer.apple.com/metal/jax/).

## What the local code actually says

Inspected `experiments/address-parser/train.py` and `export.py` as present on 2026-09-14:

- Device auto-selection chooses MPS else CPU, **never CUDA**. A later NVIDIA machine would need an explicit device or corrected auto-selection.
- The complete gzip datasets are read and Python-encoded before selecting the requested training sample. Any wrapper leaves this problem intact.
- Collation builds many small Python-created tensors and sorts only within an already-selected batch. Measure pre-encoding and length-bucketed batches before introducing orchestration.
- CRF decoding calls `.cpu()` on every timestep's backpointer tensor. This can introduce repeated accelerator-to-host synchronization; aggregate transfer is a profiling hypothesis, not yet a measured gain.
- Training reads `loss.item()` every batch and checks a device scalar in Python. On an accelerator these can synchronize. Preserve non-finite handling but investigate less frequent scalar logging and appropriate asynchronous checks.
- Checkpointing temporarily moves the live model to CPU and back. Save a detached CPU snapshot or framework checkpoint state instead of moving the training model, especially before enabling accelerators.
- The model uses `pack_padded_sequence` and `pad_packed_sequence`. Removing packing to make compilation easier is **not** a safe mechanical change to a bidirectional GRU: reverse-direction padding can change valid-token representations. Require padding-invariance and emission/path parity tests.
- The existing export selects `dynamo=False`, opset 17, and dynamic axes. This is a tested legacy export path, not the currently recommended Dynamo exporter.

These are concrete improvement targets. They are not proof the CPU experiment has a training-speed bottleneck, nor that MPS is faster for this workload.

## Actual local probe: whole-model compilation is not plug-and-play

Environment: installed `/tmp/address-model-venv`, PyTorch `2.14.0+cpu`, Linux x86-64, four PyTorch CPU threads. Lightning, Accelerate and onnxscript are not installed. No additional packages installed.

The probe invoked `torch.compile(model, backend="eager", fullgraph=True)` on the unchanged `Tagger` using a small mixed-length English/CJK batch. Graph capture failed with `torch._dynamo.exc.Unsupported` at `train.py:133`: `pack_padded_sequence` is intentionally skipped by Dynamo. It failed after approximately 2.03 seconds. This is a **graph capture compatibility test, not an Inductor throughput benchmark**. It does not prove partial compilation is impossible, nor that another implementation cannot compile.

Consequently, neither Fabric's compile integration nor a Trainer switch can be honestly advertised as a free whole-model speedup. First profile; then consider compiling just the byte encoder or CRF loss separately, with graph-break reports and matched-output checks.

Minimal reproduction from the existing environment:

```python
import sys
import torch

sys.path.insert(0, "<repo>/experiments/address-parser")
from train import Tagger, encode, batch

rows = [
    encode({"text": text}, labeled=False)
    for text in [
        "12 Main Street Springfield Illinois 62701 USA",
        "23 Saint Johns Road Cambridge CB2 1TN United Kingdom",
        "東京都渋谷区神南1丁目19番11号",
    ]
]
x, _, lengths, _ = batch(rows, "cpu")
torch.compile(Tagger(), backend="eager", fullgraph=True)(x, lengths)
```

PyTorch recommends the `torch.export`/Dynamo ONNX exporter. A separate, pinned compatibility experiment should establish whether it handles this exact model before replacing the existing working artifact path. Installing onnxscript and blindly toggling a flag is not evidence of export correctness. [Current ONNX tutorial](https://docs.pytorch.org/tutorials/beginner/onnx/export_simple_model_to_onnx_tutorial.html).

## Browser deployment constrains architecture more than Trainer selection

Inspection covered the actual saved `independent-layout-100k/export/model.onnx`: it contains **two GRU nodes**. The official ONNX Runtime WebGPU operator table at commit `3eda9022d9a57aea63a44d7266252b40fe232e9c` (2026-07-29) contains **no GRU entry**. This is a specific reason not to equate our successful Wasm run with an all-WebGPU execution path. Fallback, a compatible decomposition, or a custom implementation needs separate validation. [Pinned WebGPU operator table](https://github.com/microsoft/onnxruntime/blob/3eda9022d9a57aea63a44d7266252b40fe232e9c/js/web/docs/webgpu-operators.md).

The runtime documentation distinguishes broad Wasm operator support from the smaller GPU operator sets. Keep ONNX Runtime Wasm as a correctness reference while qualifying any smaller handwritten Wasm/WebGPU implementation. Training frameworks are absent from the deployed JavaScript package, so Trainer does not itself increase browser bytes; the graph, weights and chosen inference runtime do. [ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/).

## What to test on the user's M1 Pro 16 GB

1. Fixed eager FP32 baseline: identical cached examples, batch order, model initialization and complete evaluation. Report process plus accelerator peak memory, examples/second, epoch time including validation, and cold-start time.
2. MPS versus CPU with supported ops; report fallback explicitly. Do not assume 16 GB is all available to training: the OS, application and unified GPU allocations share it.
3. Buckets for token count/byte width, with correct padding behavior. Current Transformers MPS docs warn that distinct dynamic shapes grow the MPS graph cache; this motivates measurement, not importing Transformers into our custom project.
4. Only then test mixed precision, with the CRF log-partition/score math kept FP32 initially. The numerical accept/reject criterion is full validation and quantization/export parity, not merely a finite loss.
5. Compare a framework adapter only if it solves a demonstrated maintenance need, with checkpoint cadence, metrics and precision matched. No adapter should change the statistical experiment by accident.

PyTorch documents an opt-in CPU fallback for unsupported MPS operations; log that setting as part of the experiment. Current HF documentation describes MPS FP16/BF16 support (BF16 requiring macOS 14+) and warns about graph-cache growth. Actual support for our packed GRU/CRF must be tested on the user's machine. [PyTorch MPS environment variables](https://docs.pytorch.org/docs/2.14/mps_environment_variables.html), [current MPS guidance](https://huggingface.co/docs/transformers/perf_train_special).

A dependency lock and fixed seed still cannot promise bit-identical results across devices or PyTorch releases. Use tolerances for emissions and explicit decoded-output comparisons, and distinguish statistical reproducibility from bitwise replay. [PyTorch reproducibility](https://docs.pytorch.org/docs/stable/notes/randomness.html).

## Remaining uncertainties

No M1 Pro hardware access; no measured MLX-vs-PyTorch comparison; no measured Lightning/Fabric/Accelerate overhead; no Dynamo ONNX export attempt because its extra exporter dependency is absent; no actual browser WebGPU run. The inspected upstream pages are current as accessed, but a locked dependency combination still requires a compatibility smoke test. The current CPU model works; preserve its numerical behavior while improving project structure.
