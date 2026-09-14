# Python tooling and project structure for the browser address parser

**Superseded recommendation:** the [deeper implementation review](python-stack-deep-review.md) revises the mandatory Lightning/MLflow/DVC stack to plain PyTorch with optional lifecycle and tracking layers. It includes pinned GPU Lexer/GPU Time audits and local compatibility evidence. This document preserves the initial proposal and release snapshot.

Research date: September 14, 2026. This is a recommended migration design, not an implemented framework migration. Official documentation, upstream repositories, PyPI release metadata, and our current scripts were inspected. Dependency compatibility and training performance of the proposed combination have not yet been tested together.

**Recommendation: uv + Ruff + ty, PyTorch + Lightning, Polars/Arrow + Parquet, typed configuration, pytest, local MLflow, and DVC for dataset versions.** Keep the neural network independent of the training framework and qualify exports in the browser. Adopt released versions in a lockfile; evaluate experimental accelerators separately.

## What needs to improve in the current project

The experiment already preserves source provenance, dataset hashes, checkpoint parents, exact-span evaluation, and runtime parity. Preserve that work. The current weaknesses are structural:

- `train.py` owns tokenization, data loading, the network, CRF, evaluation, and the training loop.
- `load()` reads and encodes the entire JSONL corpus before the training limit is applied. Dataset growth increases memory even for a small sampled experiment.
- Dependency pins do not describe the complete transitive environment or platform-specific PyTorch wheels.
- Warm-starting exists, but is deliberately different from restoring optimizer and training state.
- Results are scattered across run directories; large artifacts are Git-ignored without a portable retrieval workflow.
- Browser verification currently uses Wasm under Node. Actual browser compatibility and performance remain separate work.

The recently added `expand.py` and `data/multisource/` should enter the same architecture. This proposal does not assume data acquisition is still limited to the initial three source samples.

## Development tooling

| Tool | Recommendation for this project |
| --- | --- |
| **uv** | Manage Python, dependency groups, environments, locking, package execution, and wheel builds. Commit `uv.lock`; use `uv sync --locked` in CI. [Project documentation](https://docs.astral.sh/uv/guides/projects/) |
| **uv_build** | Build our pure-Python package using the standard `src/` layout. Compiled dependencies such as PyTorch do not make our own package a native extension. Change backend only if we later write one. [Build backend](https://docs.astral.sh/uv/concepts/build-backend/) |
| **Ruff** | One formatter/linter, including import sorting. Start with correctness, imports, and modernization rules; avoid turning on every stylistic rule. [Ruff tutorial](https://docs.astral.sh/ruff/tutorial/) |
| **ty** | Adopt as the single type checker, pinned. It is still beta and may change diagnostics between releases. Audit its behavior on our tensor-heavy code; targeted suppressions or a switch to Pyright are preferable to disabling checking broadly. [Upstream status](https://github.com/astral-sh/ty#version-policy) |
| **pytest + Hypothesis** | Preserve existing assertions as tests; use generated Unicode/formatting inputs for the parser invariants. No need for a large test framework around the tests. [pytest layout](https://docs.pytest.org/en/stable/explanation/goodpractices.html), [Hypothesis](https://hypothesis.readthedocs.io/en/latest/) |
| **Typer + Pydantic v2** | A small typed CLI and validated experiment configuration. Read TOML with `tomllib`; reject unknown keys and invalid settings before expensive work. Use Pydantic at config/import boundaries, not as a Python-object allocation layer over every training token. [Typer](https://typer.tiangolo.com/), [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) |

Use Python **3.13** as the proposed new baseline, with an exact patch pinned after platform qualification. Keep the existing Python 3.11 environment available to reproduce old results. This is a compatibility choice, not a claim that 3.13 trains faster. Current PyTorch and ONNX Runtime publish CPython 3.13 Apple Silicon wheels; their inspected wheels target macOS 14+. Verify the Mac's OS before installation. [PyTorch files](https://pypi.org/project/torch/#files), [ONNX Runtime files](https://pypi.org/project/onnxruntime/#files).

Configure the Linux CPU wheel source explicitly and use the normal macOS wheel on Apple Silicon; add a separate CUDA option when actually needed. A lockfile does not make different hardware numerically identical. [uv's PyTorch integration](https://docs.astral.sh/uv/guides/integration/pytorch/).

## The training framework: choose PyTorch Lightning

Our model has a conventional supervised optimization loop even though its loss and decoder are custom. Lightning can own optimization, device handling, checkpoint callbacks, validation scheduling, and logging, while our code owns the address-specific logic. It runs locally; using it does not require Lightning Cloud. [Upstream overview](https://github.com/Lightning-AI/pytorch-lightning#why-pytorch-lightning).

Keep `AddressTagger` as an ordinary `torch.nn.Module`. Add one small LightningModule that calls its forward/loss methods, defines AdamW, and reports our metrics. Export the underlying network, not the training wrapper. Start with normal DataLoaders; a DataModule is useful only if shared loading/state handling warrants it.

Use explicit `ModelCheckpoint` configuration for best and last checkpoints. Distinguish `--init` for weights-only warm starts from `--resume` using `Trainer.fit(..., ckpt_path=...)`. Lightning restores optimizer/scheduler/loop state, but exact data-order resumption still needs a tested sampler and RNG policy. Initially promise reproducible epoch-boundary resumption, not arbitrary mid-stream resumption. [Checkpoint documentation](https://github.com/Lightning-AI/pytorch-lightning/blob/master/docs/source-pytorch/common/checkpointing_basic.rst).

Preserve our custom exact-parse metrics. Compute totals over examples rather than averaging batch percentages, and keep generated exact spans separate from public normalized field maps. Preserve gradient clipping, loss normalization, label order, and checkpoint selection during migration. A framework change should not silently become a new modeling experiment.

| Alternative | Decision |
| --- | --- |
| **Lightning Fabric** | A good lower-level alternative if the training algorithm later needs an unusual loop. Trainer currently removes more code we would otherwise maintain. [Framework comparison](https://github.com/Lightning-AI/pytorch-lightning#lightning-fabric-expert-control) |
| **Hugging Face Accelerate** | Useful device/distributed plumbing around a loop we own. Less compelling than Trainer for our present need for a standard lifecycle. Do not stack both. [Migration guide](https://huggingface.co/docs/accelerate/main/en/basic_tutorials/migration) |
| **Transformers Trainer** | Reconsider if the primary task becomes fine-tuning Hugging Face transformer models. Our byte CNN/GRU/CRF does not need that ecosystem's model conventions. |
| **MLX** | Interesting Apple Silicon experiment; its unified memory design fits the Mac. A rewrite would also need a separately verified export route. Keep PyTorch as the reference until an end-to-end benchmark justifies migration. [MLX](https://ml-explore.github.io/mlx/build/html/) |

Lightning is an engineering choice, not an accuracy or throughput guarantee. Check its overhead on our small network.

## Data processing and memory

Use **Parquet as the prepared dataset format**, **Polars for lazy filtering/joins/audits**, and the already-used **PyArrow for bounded record batches**. Retain raw snapshots and small JSONL audit examples. Polars supports streaming execution, but some operations fall back to in-memory processing; inspect joins and global deduplication rather than assuming constant memory. [Polars streaming](https://docs.pola.rs/user-guide/concepts/streaming/), [Arrow Parquet](https://arrow.apache.org/docs/python/parquet.html).

The pipeline should be explicit:

```text
pinned sources → validated component records → grouped splits
               → labeled formatting variants → immutable Parquet shards
               → bounded training batches → checkpoints → evaluation → browser export
```

Keep source ID, original/base ID, geographic group, label provenance, mapping version, split, country, text, and raw spans in prepared records. Unlabeled rows must remain unlabeled; do not turn absent annotations into negative/O labels. Preserve quarantine/exclusion reports.

Select the experiment's rows before encoding them. Stream selected shards or read bounded Arrow batches through a PyTorch dataset, with an explicit shuffle seed and finite epoch length. If using an IterableDataset, shard it across workers so increasing `num_workers` cannot duplicate training examples. Start with zero workers on the Mac, then measure. [PyTorch data API](https://docs.pytorch.org/docs/2.14/data.html).

Cache deterministic encoding only when profiling shows it matters. Key the cache by dataset, tokenizer, label schema, limits, and gap-feature version. Do not put millions of nested Python lists into every worker. PyArrow's typed representation is for data storage; it does not by itself eliminate model batching work.

## Reproducibility and experiment tracking

**MLflow locally** gives us searchable runs, learning curves, parameters, and linked artifacts. Configure a local SQLite backend and local artifact directory explicitly. Log source/dataset/config/code hashes as well as accuracy, country regressions, parameter count, weight bytes, complete download bytes, and browser timings. Keep machine-readable evaluation JSON portable outside the tracking UI. No hosted account is necessary. [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/).

**DVC** should version prepared datasets and define the small prepare → train → evaluate → export pipeline. Git stores the manifests and DVC metadata; the large bytes live in an explicitly configured artifact store. A local cache alone is not a backup. Avoid duplicating every checkpoint into both DVC and MLflow: use DVC for data/pipeline lineage and MLflow for run artifacts. Track upstream snapshot identities without automatically retaining every giant public archive. [DVC pipeline files](https://doc.dvc.org/user-guide/project-structure/dvcyaml-files).

Use one literal TOML file per named experiment initially, with resolved settings copied into every run. **Hydra** becomes useful when we genuinely need composable data/model/hardware configurations; we do not need a second configuration system today. **Optuna** comes after a stable evaluation protocol and a bounded search budget. [Hydra](https://hydra.cc/docs/intro/), [Optuna](https://optuna.readthedocs.io/en/stable/).

## Proposed repository layout

Give this work its own project root instead of tying its imports or environments to the personal website. A separate repository is a sensible eventual home; no repository move is performed by this research.

```text
address-parser/
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── configs/
│   ├── baseline.toml
│   └── multisource.toml
├── src/address_parser/
│   ├── __init__.py
│   ├── cli.py               # prepare, audit, train, evaluate, export, predict
│   ├── config.py            # validated settings
│   ├── schema.py            # field order, spans, provenance
│   ├── data/
│   │   ├── sources.py       # existing acquisition/import functions
│   │   ├── prepare.py       # mapping, splits, augmentation
│   │   └── dataset.py       # bounded reading and collation
│   ├── tokenizer.py         # versioned bytes and source offsets
│   ├── model.py             # plain PyTorch network + CRF
│   ├── train.py             # thin Lightning integration
│   ├── evaluate.py          # exact metrics and paired diagnostics
│   ├── teacher.py           # development-only native libpostal integration
│   └── export.py            # inference-only artifacts and parity fixtures
├── tests/                   # existing invariants plus migration checks
├── web/                     # TypeScript runtime, own JS lockfile, browser tests
├── manifests/               # source, data and split versions; tracked
├── data/                    # immutable snapshots/shards; large files external
├── runs/                    # checkpoints and run artifacts; large files external
├── reports/                 # selected compact results and model cards
├── docs/                    # research and experiment decisions
├── dvc.yaml                 # introduced with the reproducible pipeline
├── dvc.lock
└── .github/workflows/ci.yml
```

This is one Python package. Introduce a uv workspace only when there are genuinely separate Python packages. Do not create a generic multi-model registry or empty phone-model implementation. Keep existing `Tagger` state-dict names compatible when moving code so old checkpoints remain readable.

Use dependency groups: `dev` for Ruff/ty/tests; `tracking` for local MLflow; `pipeline` for DVC; `analysis` for optional marimo. Export dependencies can be an optional extra. The model and tokenizer modules must not import tracking, acquisition, or Lightning on import. **marimo** is a good optional Python-file notebook for error exploration; training continues through the package CLI. [marimo](https://docs.marimo.io/).

## Performance and browser qualification

On the M1 Pro, first establish float32 CPU and MPS correctness and throughput. Report peak memory, examples/second, and time to a fixed accuracy. MPS can fall back to CPU for unsupported operators when enabled; record that explicitly. A small recurrent model with CPU-side packing/decoding may not benefit from device changes as much as expected. [MPS environment variables](https://docs.pytorch.org/docs/2.14/mps_environment_variables.html).

Profile loading, byte encoding, padding, recurrent work, and CRF decoding separately. Test length-aware batches only with a controlled shuffle policy. Treat mixed precision and `torch.compile` as measured experiments, not defaults. This project's dynamic sequences and CRF reductions need numerical and speed checks.

PyTorch now recommends the `torch.export`-based ONNX exporter (`dynamo=True`). Our existing exporter uses the older path and has measured parity. Test the new path on the actual packed bidirectional GRU before changing it; preserve the working exporter until replacement parity passes. [Current ONNX guidance](https://docs.pytorch.org/tutorials/beginner/onnx/export_simple_model_to_onnx_tutorial.html).

Keep Python → ONNX CPU → web Wasm → actual browser checks. WebGPU operator coverage differs from Wasm, so treat it as a separate backend qualification. The browser package must contain only inference assets; Python training dependencies never ship to users. Measure tokenizer/decoder/runtime/weights together, including cold start and download size. [ONNX Runtime Web](https://onnxruntime.ai/docs/get-started/with-javascript/web.html).

## Migration sequence and checks

1. Package the existing code and lock its current Python 3.11 environment first. Preserve checkpoint outputs and data hashes.
2. Add Ruff, ty, and focused pytest tests. Test spans, Unicode/UTF-16 conversion, BIO validity, leakage, and a tiny overfit; use Hypothesis where generated edge cases improve coverage.
3. Replace eager loading with bounded prepared-data access. Verify selected row IDs, label counts, and fixed evaluation outputs before changing the training framework.
4. Adopt Lightning with identical model/loss/optimizer settings. Check interrupted/resumed versus uninterrupted training at epoch boundaries, then run one matched real experiment.
5. Add local tracking and DVC lineage. Qualify Python 3.13 and MPS separately, retaining historical environments.
6. Add real browser tests and a release artifact manifest. Run full training/benchmarks explicitly; ordinary CI uses small fixtures and CPU tests.

Proposed daily commands after migration:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv run address-parser train --config configs/baseline.toml
uv run address-parser evaluate --run runs/<id>
uv run address-parser export --run runs/<id>
```

CI should additionally build/install the wheel and test from outside the source directory. Smoke-test the supported Mac and Linux environments; run full corpus audits and browser benchmarks as separate jobs. Seeds and lockfiles are necessary, but do not promise bit-identical CPU/MPS results.

## Release snapshot

These versions were returned by PyPI on the research date, not jointly installed or qualified. Link targets identify the exact releases; the eventual `uv.lock` should capture tested transitive versions.

| Package | Observed release |
| --- | --- |
| uv | [0.12.13](https://pypi.org/project/uv/0.12.13/) |
| Ruff | [0.16.7](https://pypi.org/project/ruff/0.16.7/) |
| ty | [0.0.80, beta](https://pypi.org/project/ty/0.0.80/) |
| PyTorch | [2.14.0](https://pypi.org/project/torch/2.14.0/) |
| Lightning | [2.6.6](https://pypi.org/project/lightning/2.6.6/) |
| Polars / PyArrow | [1.44.2](https://pypi.org/project/polars/1.44.2/) / [25.0.1](https://pypi.org/project/pyarrow/25.0.1/) |
| Pydantic / Typer | [2.13.5](https://pypi.org/project/pydantic/2.13.5/) / [0.27.2](https://pypi.org/project/typer/0.27.2/) |
| MLflow / DVC | [3.16.0](https://pypi.org/project/mlflow/3.16.0/) / [3.67.1](https://pypi.org/project/dvc/3.67.1/) |
| pytest / Hypothesis | [9.1.1](https://pypi.org/project/pytest/9.1.1/) / [6.168.0](https://pypi.org/project/hypothesis/6.168.0/) |
| ONNX / ONNX Runtime | [1.22.0](https://pypi.org/project/onnx/1.22.0/) / [1.30.0](https://pypi.org/project/onnxruntime/1.30.0/) |
| marimo / Optuna, optional | [0.24.2](https://pypi.org/project/marimo/0.24.2/) / [5.0.0](https://pypi.org/project/optuna/5.0.0/) |
