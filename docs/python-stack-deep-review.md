# Engineering a small browser model project

## Decision

Build an installable Python research package around **plain PyTorch**, with **uv, Ruff, pinned ty, pytest/Hypothesis, and optional prek hooks**. Use **Polars and Arrow/Parquet for the auditable dataset**, and a versioned, compact encoding cache for repeated training when it is beneficial. Treat the browser runtime and exported model contract as first-class parts of the repository.

Lightning Trainer is a credible option, but it should not be mandatory for the current single-model project. Introduce **Fabric** when device/precision/launch code needs standardization, or **Trainer** when repeated training lifecycles justify its ownership of the loop. Neither is a substitute for trustworthy data, correct checkpoint state, or browser parity. Tracking and pipeline products should have explicit jobs: start with portable run records, choose one tracking workflow, and add dataset artifact management where retrieval is required.

This recommendation is for the address parser's current byte-CNN, bidirectional GRU, and constrained CRF, trained locally or on a single accelerator and ultimately delivered as a small browser library. It does not assume transformer fine-tuning, distributed training, or a server inference product. Evidence was checked against September 2026 documentation and pinned reference repositories. Proposed migrations and cross-platform performance remain unqualified until executed.

## What constitutes a robust framework for this work

There are four distinct responsibilities. Combining them under one product name obscures the actual requirements.

| Responsibility | Required result | Appropriate mechanism |
| --- | --- | --- |
| Numerical training | Correct forward/backward pass and optimization | PyTorch; optional Fabric/Trainer |
| Data experiments | Traceable sources, consistent labels, reproducible splits and mixtures | Typed data contracts, Parquet, manifests, explicit preparation stages |
| Experiment lifecycle | Recoverable runs, comparable evaluations, retrievable artifacts | Checkpoint/run contract; optional local MLflow or DVC/DVCLive |
| Browser delivery | Correct, fast, small inference on supported browsers | Versioned export contract, runtime implementation, parity and performance tests |

The framework should reduce code that repeatedly causes problems. The current project's most important gaps are eager dataset materialization, coupled responsibilities inside `train.py`, incomplete resumption semantics, and browser qualification. Merely moving the same functions into a Trainer does not resolve those gaps.

## Training framework comparison

The [reference implementation audit](gpu-reference-tooling-audit.md) and [training framework audit](training-framework-audit.md) contain the detailed pinned code links, executed test results, and compatibility-probe method behind the recommendations below.

| Candidate | Benefit | Cost or limitation for this project | Decision |
| --- | --- | --- | --- |
| **Plain PyTorch** | Direct control over our existing loop and numerical behavior | Checkpoint, logging, and sampler state remain explicit responsibilities | **Default for the next migration** |
| **Lightning Fabric** | Standardizes accelerator/precision/distributed mechanics while retaining a custom loop | Still requires lifecycle and evaluation code | First optional training layer |
| **Lightning Trainer** | Owns validation scheduling, callbacks, optimizer lifecycle, and checkpoint integration | Changes loop ownership and default behavior; no demonstrated speed gain here | Adopt when lifecycle reuse earns it |
| **Accelerate** | Adapts existing PyTorch loops for devices and distributed execution | Overlaps Fabric; does not remove all custom lifecycle work | Alternative to Fabric, not an additional layer |
| **Transformers Trainer** | Useful conventions for transformer fine-tuning | Does not match the current model family particularly well | Revisit if that workload appears |
| **MLX** | Apple-oriented array/training framework | Requires model and export-path qualification; Mac speed cannot be assumed | Separate experiment only |

Lightning and Accelerate document different levels of loop ownership; none establishes a throughput advantage for this specific network.[^1][^2] MLX's unified-memory design is relevant to Apple Silicon, but selecting it would create another numerical implementation to verify.[^3]

Keep the network an ordinary `nn.Module` regardless of the loop choice. Data preparation, evaluation, and export must remain callable without starting a Trainer. Preserve the CRF loss normalization, gradient clipping, label order, and checkpoint ranking during refactoring. A small, explicit training entry point with tested state handling is a substantial improvement over loose scripts without creating a general-purpose training framework.

### Concrete findings in the existing model

The current `auto` device branch selects MPS when available and CPU otherwise; it does not select CUDA. The decoder copies backpointers to CPU during its sequence loop, training extracts scalar loss each batch, and checkpoint saving temporarily moves the live network to CPU. These operations warrant profiling before any accelerator-speed claim. Their cost was not measured on an M1 Pro or CUDA device.

A bounded CPU probe with PyTorch 2.14, four threads, 512 prefix-selected addresses, batch size 64, five warm-up batches, and forty timed batches measured:

| Operation | Observation |
| --- | ---: |
| Encode the 512 records once | 64.13 ms |
| Prepare a batch, median | 2.99 ms |
| Forward, CRF loss, backward, clipping, AdamW step, median | 63.95 ms |

This uses a fresh model, a small nonrepresentative sample, and warm data. It is not a training-framework comparison or a Mac benchmark. It indicates that **the eager loader's memory problem should not be confused with proof that batch preparation dominates steady-state CPU training**. Use `torch.profiler` and representative length distributions to investigate further.[^4]

A separate `torch.compile(..., backend="eager", fullgraph=True)` probe failed at `pack_padded_sequence`, which Dynamo deliberately skips. This is a whole-graph capture failure, not proof that partial compilation or a different model cannot help. The current saved ONNX graph contains two GRU nodes; the pinned ONNX Runtime WebGPU operator list contains no GRU entry. A Trainer change does not remove those nodes or supply a WebGPU kernel. Retain the tested Wasm path and separately investigate fallback, decomposition, or a different architecture.[^29]

Machine-readable observations: [CPU timing probe](evidence/address-tooling-timing.json) and [compile/export probe](evidence/framework-compile-probe.json). No cross-framework speed comparison or Mac measurement was performed.

## GPU Lexer and GPU Time: what to adopt

The inspected repositories are pinned to GPU Lexer `1e514fd681e31d6b19296f985fb01d8fdc0ae74f` and GPU Time `4c5058c55a72e38d129f490297777762ba618a33`. Their code demonstrates a compact training-to-product workflow with important qualification machinery. Neither uses Lightning, Accelerate, Hydra, MLflow, or DVC in the inspected training path. Their framework choices establish feasibility, not the superiority of custom loops.[^30][^31]

| Concern | GPU Lexer | GPU Time | Transferable decision |
| --- | --- | --- | --- |
| Python environment | venv/pip, a PyTorch version range | uv lock; Python 3.13; torch/numpy | Use a tested uv environment |
| Training | Plain PyTorch, JavaScript orchestration | Plain PyTorch, pnpm invoking uv | Keep the numerical core independent |
| Prepared input | Memory-mapped binary arrays | Eager binary arrays | Separate auditable records from training representation |
| Batches | Length grouping and measured token budgets | Length buckets | Control padding; measure actual hardware |
| Inference | Custom WebGPU | JavaScript CPU plus WebGPU | Choose by workload and package constraints |
| Evidence | Source/corpus metadata and active artifacts | Source/data hashes, checkpoint history, candidate comparisons | Make every result attributable to immutable inputs |

### Shared preprocessing is part of model correctness

GPU Time's featurizer uses the deployed TypeScript tokenizer and label definitions to produce Python training inputs. It rejects misaligned supervision and records structural fingerprints. The central lesson is that preprocessing equivalence is tested or shared, rather than assumed from matching function names.[^32]

For multilingual addresses, define one explicit specification and cross-language corpus covering combining marks, CJK, emoji, punctuation, whitespace, and offset conversion. Sharing executable preprocessing is one option; maintaining Python and TypeScript implementations with comprehensive conformance fixtures is another. A featurizer change must invalidate cached tensors and trigger export tests even if the network dimensions are unchanged.

### Efficient batching is a measured choice

GPU Lexer's loader uses `torch.from_file`, and its batch-budget comparison warms up and synchronizes accelerators before timing. GPU Time's use of `np.fromfile` is an eager load, not a memory-map implementation. It is therefore inaccurate to describe both projects as sophisticated streaming systems. They use different practical solutions for their data sizes.[^33][^34]

Length grouping can reduce wasted work in the address model, but must preserve intended example weighting and order randomization. For a bidirectional GRU, removing packing merely to simplify compilation can change valid-token representations through reverse-direction padding. A throughput change must preserve the padding-invariance test and the statistical experiment.

### Evaluate the actual deployed artifact

GPU Time exports quantized weights, reconstructs the serialized artifact for evaluation, and evaluates end-to-end decoded results before candidate promotion. It also retains artifact/source identities. Its network is engineered for its runtime, including an affine recurrence that supports a parallel scan; that is materially different from a standard GRU.[^35][^36]

The address release process should likewise evaluate the deserialized quantized artifact with its actual decoder. Matching float loss or token accuracy is insufficient. Calibration and candidate selection must use designated development data; naming a split `heldout` does not make it untouched once it is used to tune thresholds.

### GPU execution is not always the appropriate default

GPU Time's automatic mode routes work to GPU at 32 jobs or 512 tokens; smaller requests stay on CPU. That threshold is a project-specific policy, not a performance result for address parsing. It shows why batch throughput and single-input latency need separate experiments.[^37]

Neither inspected reference ships ONNX Runtime or Wasm. Their compact bespoke runtimes explain part of their small-package story. The address project can retain ONNX as a correctness reference while deciding whether runtime specialization earns its implementation cost.

### Preserve the lessons, including the shortcomings

GPU Time's export code allows some statistically nonsignificant regressions, despite stricter language in parts of its model card. It checks paired changed outcomes and minimum support. That is not a guarantee that every family improves, and nonsignificance is not proof of noninferiority. Its history also documents evaluating argmax while production used Viterbi, showing why decoder-consistent metrics matter.[^38][^39]

Both repositories provide more verification commands than their default CI runs. The inspected CI workflows do not execute Python training tests or explicit browser-GPU parity. GPU Time's Python tests were run separately on Linux CPU: 28 model tests passed; eight decoder tests passed and one MPS test was skipped. This was the existing Python 3.11/PyTorch 2.14 environment, not a reproduction of its locked Python 3.13 environment or a browser benchmark.[^40][^41]

The address project should make essential cross-language checks explicit CI jobs and preserve an independent final evaluation collection. Source weighting, new synthetic families, and teacher agreement must remain experiments with country/field regressions visible. A successful reference implementation supplies engineering patterns, not permission to copy its known gaps.

## Data: an auditable table and a training representation

Use Parquet as the authoritative prepared record format. Preserve original text, component spans, source IDs, original/variant linkage, geographic group, split, country, label provenance, and mapping version. Polars is well suited to projection, filtering, coverage counts, and joins; Arrow supports record-batch access. Streaming queries can still contain memory-intensive operators, so inspect the physical plan and use streaming sinks rather than collecting a massive result into RAM.[^5][^6]

The training representation has a different job. It should make repeated epochs efficient without losing the ability to trace a token back to its source. For a selected finite corpus, a compact array cache can store concatenated byte IDs, token offsets, labels, and example boundaries. Memory mapping is an option once repeated encoding or resident Python objects justify the extra representation. The cache is disposable and must be keyed by dataset hash, tokenizer version, field schema, encoding limits, and augmentation settings. PyTorch provides file-backed tensors; mapping a file is not the same as placing its whole contents on the accelerator.[^7]

Do not overwrite raw text to make storage convenient. Do not reconstruct official address truth from a lossy simplified label schema. Unlabeled examples, teacher labels, generated labels, and independent annotations remain distinguishable through every stage.

### Loader options

| Option | Useful here | Boundary |
| --- | --- | --- |
| **Arrow batches + PyTorch Dataset** | Local immutable address shards, explicit selected IDs | Some batching/sampling code remains ours |
| **Hugging Face Datasets** | Convenient acquisition, partition selection, Arrow-backed data, streaming | Streaming shuffle/resume has specific semantics; do not infer exact replay |
| **TorchData StatefulDataLoader** | Saving sampler/worker state for interruption recovery | Dataset state must be implemented correctly; worker topology matters |
| **LitData** | Managed streaming, caching, and larger remote-data workloads | Adds another data layer; qualify benefits before converting local data |
| **WebDataset** | Particularly useful for collections of binary examples | Adds little to the present structured-text/Parquet workload |

Hugging Face documents that resuming a shuffled stream loses buffered examples and refills the buffer. That matters when comparing a resumed run with an uninterrupted run.[^8] TorchData supports dataset/sampler state, including aggregation of worker state, but its iterable examples require the same worker count when restoring.[^9] LitData is a credible streaming alternative; its published general speed claims are not measurements of this parser.[^10]

For the next dataset size, select a finite set of original IDs and generate a deterministic epoch permutation. Save that selection and its ordering policy. This gives a simpler basis for exact experiment comparisons than training from a mutable remote stream. Start with epoch-boundary recovery; introduce mid-epoch recovery only with a test of the remaining example IDs and resulting optimizer trajectory.

## Developer tooling worth adopting

**uv and uv_build** should replace ad hoc environment installation with a package, lockfile, explicit dependency groups, and reproducible commands. Keep the established Python 3.11 environment for historical results; qualify Python 3.13 as a separate environment change. Configure CPU/CUDA/Mac package sources explicitly. In CI, use `--locked` to detect stale dependency metadata; `--frozen` does not provide the same freshness check. Pin the uv release and CI actions.[^11][^12]

**Ruff** remains the formatter and linter. **ty** is an appropriate modern checker for this codebase, but its beta status makes version pinning and deliberate updates important. It checks Python types, not tensor-shape or numerical correctness. Retain runtime shape/span assertions where they protect the model contract.[^13][^14]

**prek** is a relevant addition to the earlier shortlist: it is a Rust implementation compatible with pre-commit hook configurations and integrates with uv. Use it to run the same lightweight checks developers can run directly; CI remains authoritative. Do not put full-corpus downloads or training in a commit hook.[^15]

**pytest and Hypothesis** cover distinct needs: ordinary example tests for checkpoint/export regressions and generated Unicode/formatting cases for invariants. The invariant must be defensible: adding whitespace can change a parse, but returned spans must still refer to the exact original input. Avoid declaring every augmentation semantically equivalent merely because a generator can produce it.[^16]

**Pydantic plus TOML** is suitable for validating configuration and artifact metadata. Define unknown-key rejection, cross-field constraints, and explicit precedence of defaults/config/CLI overrides. Do not instantiate rich validation objects per tensor element or per token. Pydantic's own guidance distinguishes validated boundary processing from unnecessary repeated work.[^17] Retain argparse during packaging if it already does the job; Typer is an optional CLI improvement, not a prerequisite for model quality.

**marimo** remains a good optional analysis interface for country errors and candidate comparisons. It should import package functions, not contain the sole implementation of training or data preparation. Hydra and Optuna are justified when configuration composition or bounded hyperparameter search becomes a real workload, respectively; neither is required to compare two controlled experiments.

## Tracking and orchestration: choose responsibilities explicitly

The foundational artifact is a portable run directory containing resolved configuration, immutable source/data identities, code identity including dirty changes, environment, seed/sampler policy, checkpoint lineage, evaluation outputs, and export reports. A dashboard indexes this information; it must not be the only place it exists.

| System | Appropriate reason to adopt | Recommendation |
| --- | --- | --- |
| **Local MLflow** | Searchable comparisons, curves, parameters, and artifacts | Best optional interactive tracker; keep tracking local unless publishing is intended |
| **DVC + DVCLive** | Git-linked prepared-data versions, stage dependencies, metrics | Coherent alternative when data/pipeline reproducibility is the immediate priority |
| **Weights & Biases** | Shared hosted collaboration and artifact workflows | Consider when collaboration requires it; offline logging does not itself provide a hosted UI |
| **Kedro** | Reusable data catalogs and many structured pipelines | Worth reconsidering with multiple production data pipelines |
| **Dagster** | Persistent asset orchestration, partitions, schedules, backfills | Defer until data refresh operations need an orchestrator |
| **Prefect** | Retryable asynchronous workflows and remote execution | Defer until acquisition/training is a managed recurring workflow |

MLflow, DVCLive, and W&B all provide tracking capabilities, but do not need to be installed together.[^18][^19][^20] Kedro organizes catalogs and pipelines, Dagster centers assets, and Prefect offers task/flow execution with caching and retries. These address broader operations than a single local training experiment.[^21][^22][^23]

DVC can coexist with MLflow if DVC owns datasets and MLflow owns run artifacts. That split is useful only when both responsibilities exist; the default should not duplicate every weight file and metric into two registries. Configure actual artifact storage and verify restoration from a clean directory. Hashes prove identity, not availability, and a local cache is not a backup.

Prefect's cache behavior is a useful caution even if it is not adopted: inputs and task source are only part of a correct cache identity. Address-label mapping, source revision, random seed, and preprocessing schema may live outside a function body. Framework caching does not automatically capture the full scientific dependency graph.[^23]

## The browser contract drives the architecture

A release should bind weights to their architecture, tensor shapes, label IDs, byte vocabulary, feature version, quantization scales, decoder parameters, input limits, offset convention, and status behavior. A model file without that contract is incomplete. Include fixtures containing model inputs, expected emissions or suitable tolerances, decoded labels, and source spans.

The current model has 615,244 parameters and a recurrent encoder/CRF. The reference projects use much smaller feed-forward convolutional models. Their runtime strategy is instructive, but their kernel simplicity and package sizes cannot be transferred by assumption. A different address architecture is a separate accuracy/latency experiment, not a repository refactor.

Maintain an ONNX reference path while comparing final delivery options: standard ONNX Runtime Web, a reduced custom build, or a narrowly implemented runtime. ONNX Runtime's deployment documentation explicitly includes JavaScript, Wasm, and model assets; importing the Wasm-only entry point can reduce JavaScript overhead, but does not remove the Wasm engine.[^24]

Quantization frameworks also need deployment qualification. PyTorch-side low-bit kernels do not automatically exist in Wasm or WebGPU. Stored int8 followed by dequantization is a storage strategy, not evidence of integer inference speed. Safe tensor serialization can be useful for interchange, but it is not an optimizer/sampler checkpoint format or a browser engine.[^25][^26]

Measure single-address cold initialization and latency separately from large-batch throughput. Use worker execution where it improves UI responsiveness, and report main-thread blocking, peak memory, download bytes, warm/cold timing, and fallback behavior. Backend GPU timing, host preprocessing, upload, readback, and decoding are distinct costs. ONNX Runtime documents profiling limitations and ways to inspect execution.[^27]

Playwright can automate browser tests, but its WebKit build is not a complete substitute for release Safari on the M1 Pro. Likewise, software-backed/headless WebGPU is not representative hardware performance. Record browser version, selected adapter/backend, threading settings, and whether the intended accelerator actually executed.[^28]

## Project structure and qualification

Use a single Python package with an independently buildable browser package:

```text
address-parser/
├── pyproject.toml / uv.lock / .python-version
├── src/address_parser/
│   ├── cli.py / config.py / schema.py
│   ├── data/          # acquisition, mapping, splits, encoding cache
│   ├── tokenizer.py
│   ├── model.py       # plain PyTorch, no tracker/framework imports
│   ├── train.py       # one explicit training entry point
│   ├── evaluate.py / teacher.py / export.py
├── configs/           # experiment settings
├── manifests/         # source and prepared-data identities
├── contracts/         # export schema and cross-language fixtures
├── tests/             # focused Python correctness checks
├── web/               # runtime, own JS lockfile, browser tests
├── benchmarks/        # repeatable timing/memory protocols
├── reports/           # compact comparison results and model cards
├── docs/
└── data/ + runs/      # large artifacts managed separately from Git
```

The separation is by responsibility, not by speculative abstraction. Do not create empty registries for future model families. If phone parsing becomes an implemented task, share only contracts/utilities that demonstrably overlap; the two tasks need different data and correctness definitions.

Before migrating the training framework, demonstrate that packaging alone preserves a fixed checkpoint's predictions. Then change the data representation while preserving selected rows and labels. Only then alter the loop or hardware. A clean wheel installation outside the repository should run the same smoke test, so relative imports and accidental development dependencies are caught.

CI should cover four levels: fast static checks, numerical/data invariants, export parity, and separately scheduled full evaluation/browser benchmarks. Keep public benchmarks out of ordinary model selection once designated final tests; the currently inspected public suite remains development evidence. Use predeclared limits on important country/field regressions, not just global accuracy. Statistical tests on paired errors can supplement the policy, but a nonsignificant regression does not establish equivalence, especially in small or correlated slices.

## Sources

[^1]: Lightning AI. [PyTorch Lightning and Fabric](https://github.com/Lightning-AI/pytorch-lightning), current upstream documentation, consulted September 2026.
[^2]: Hugging Face. [Add Accelerate to your code](https://huggingface.co/docs/accelerate/main/en/basic_tutorials/migration).
[^3]: Apple ML Research. [MLX documentation](https://ml-explore.github.io/mlx/build/html/).
[^4]: PyTorch. [Profiler API, 2.14](https://docs.pytorch.org/docs/2.14/profiler.html).
[^5]: Polars. [Streaming execution](https://docs.pola.rs/user-guide/concepts/streaming/).
[^6]: Polars. [Streaming Parquet sink](https://docs.pola.rs/api/python/stable/reference/api/polars.LazyFrame.sink_parquet.html).
[^7]: PyTorch. [File-backed tensors, 2.14](https://docs.pytorch.org/docs/2.14/generated/torch.from_file.html).
[^8]: Hugging Face. [Datasets 4.8.4 streaming and checkpoint limitations](https://huggingface.co/docs/datasets/v4.8.4/stream).
[^9]: TorchData. [Stateful DataLoader tutorial](https://meta-pytorch.org/data/main/stateful_dataloader_tutorial.html).
[^10]: Lightning AI. [LitData](https://github.com/Lightning-AI/litdata).
[^11]: Astral. [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).
[^12]: Astral. [uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/).
[^13]: Astral. [Ruff](https://docs.astral.sh/ruff/).
[^14]: Astral. [ty version policy](https://github.com/astral-sh/ty#version-policy).
[^15]: prek maintainers. [prek](https://github.com/j178/prek).
[^16]: Hypothesis. [Documentation](https://hypothesis.readthedocs.io/en/latest/).
[^17]: Pydantic. [Performance guidance](https://docs.pydantic.dev/latest/concepts/performance/).
[^18]: MLflow. [Experiment tracking](https://mlflow.org/docs/latest/ml/tracking/).
[^19]: DVCLive maintainers. [DVCLive](https://github.com/treeverse/dvclive).
[^20]: Weights & Biases. [Experiment API and offline operation](https://docs.wandb.ai/models/ref/python/experiments).
[^21]: Kedro. [Documentation](https://docs.kedro.org/en/stable/).
[^22]: Dagster. [Assets](https://docs.dagster.io/guides/build/assets).
[^23]: Prefect. [Caching workflow outputs](https://docs.prefect.io/v3/how-to-guides/workflows/cache-workflow-steps).
[^24]: ONNX Runtime. [Deploying ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/deploy.html).
[^25]: PyTorch. [torchao](https://docs.pytorch.org/ao/stable/index.html).
[^26]: Hugging Face. [Safetensors](https://huggingface.co/docs/safetensors/index).
[^27]: ONNX Runtime. [Web performance diagnosis](https://onnxruntime.ai/docs/tutorials/web/performance-diagnosis.html).
[^28]: Microsoft. [Playwright browsers](https://playwright.dev/docs/browsers).
[^29]: Microsoft. [ONNX Runtime WebGPU operators](https://github.com/microsoft/onnxruntime/blob/3eda9022d9a57aea63a44d7266252b40fe232e9c/js/web/docs/webgpu-operators.md), pinned July 29, 2026 revision.
[^30]: Vercel Labs. [GPU Lexer Python requirements](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/requirements-torch.txt) and [orchestration](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/torch-runner.js).
[^31]: Arik Chakma. [GPU Time Python project](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/pyproject.toml) and [lockfile](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/uv.lock).
[^32]: Arik Chakma. [GPU Time featurizer](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/src/featurize.ts).
[^33]: Vercel Labs. [GPU Lexer training and batch-budget timing](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/torch/train.py).
[^34]: Arik Chakma. [GPU Time training](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/train.py).
[^35]: Arik Chakma. [GPU Time artifact export](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/export.py#L703).
[^36]: Arik Chakma. [GPU Time model](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/model.py).
[^37]: Arik Chakma. [GPU Time runtime routing](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/core/src/tagger.ts#L121).
[^38]: Arik Chakma. [GPU Time candidate guard](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/export.py#L189).
[^39]: Arik Chakma. [GPU Time model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md).
[^40]: Arik Chakma. [GPU Time CI](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/.github/workflows/ci.yml).
[^41]: Vercel Labs. [GPU Lexer CI](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/.github/workflows/ci.yml).
