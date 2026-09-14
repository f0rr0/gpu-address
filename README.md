# gpu-address

Small postal-address models trained in Python and run in the browser with TypeScript and ONNX Runtime Web.

| Location | Purpose |
| --- | --- |
| `packages/training/` | Data preparation, PyTorch training, evaluation and export |
| `packages/core/` | npm runtime; see its [API](packages/core/README.md) |
| `tests/` | Data, training and Python–Wasm parity checks |
| [docs/](docs/README.md) | Research and experiment results |
| `data/`, `runs/` | Local datasets and checkpoints, excluded from Git |

A future website belongs in `apps/`.

## Development

Python 3.11 and Node 22+. Linux uses CPU PyTorch; macOS uses the standard wheel with MPS support.

```sh
uv sync --all-extras --locked
npm ci
npm test
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

CI runs these checks and builds the Python wheel. Run commands here, or set `GPU_ADDRESS_HOME` to this directory.

```sh
uv run gpu-address train --data data/multisource --run runs/new-run --limit 100000 --dev-limit 6000
uv run gpu-address predict runs/continuation-100k/best.pt '12 Main Street, London'
uv run gpu-address export --run runs/continuation-100k --data data/layout-independent
uv run gpu-address check --data data/multisource
npm run test:parity -- runs/continuation-100k/export
```

Use `gpu-address --help` for commands and `gpu-address COMMAND --help` for options. `teacher` requires native libpostal. `--init` loads weights with a fresh optimizer; it does not resume training exactly.

## Model limits

The 615,244-parameter GRU model currently runs on **Wasm**. WebGPU and browser performance remain unqualified. Predictions are `unassessed` field assignments, not address validation. Python offsets count Unicode code points; JavaScript offsets count UTF-16 code units.
