> Historical experiment notes. For current commands and layout, see [gpu-address](../README.md).

# Address parser experiment

A working research pipeline, trained checkpoints, and an early WebAssembly inference check. This is **not a qualified replacement for libpostal**. The current model assigns fields; input rejection, ambiguity handling, and independent real-input accuracy remain unfinished.

## Files and data

| File | Purpose |
| --- | --- |
| `prepare.py` | Download bounded, checksummed source snapshots; import labels; partition streets/identities; generate variants; collect real strings and annotation material |
| `expand.py` | Acquire additional sources, audit schema/quality, and construct a separate filtered corpus |
| `check.py` | Span reconstruction, Unicode, case/layout independence, CRF brute-force comparison, padding parity, tiny overfit, and full split checks |
| `train.py` | Byte CNN → two-layer bidirectional GRU → constrained BIO CRF; 615,244 parameters at the default width |
| `teacher.py` | Run a pinned native libpostal build; preserve pseudo-labels separately; measure its public-benchmark result |
| `export.py` | ONNX export, numerical parity, stored-int8 comparison, and public-benchmark evaluation |
| `wasm-check.mjs` | Run ONNX Runtime Web's Wasm engine under Node; check JS tokenization, CRF paths and UTF-16 spans |
| `predict.py` | Inspect a saved model on one input |
| `diagnose.py` | Fixed-set field/country errors, training-sample fit, decoder comparison, and paired regressions |

Raw data and run artifacts are ignored by Git but retained locally. The previous corrected corpus is `data/layout-independent/`. `data/` and `data/expanded/` preserve earlier experiment versions, including the augmentation control that performed poorly. Their shared raw snapshots live in `data/raw/`.

`data/multisource/` adds audited samples from Senzing, Deepparse worldwide, BAN, and a documented 2022 G-NAF conversion. It contains 496,978 training rows and keeps the old development/public sets unchanged. See the [source-quality audit](address-source-quality-audit.md) for source exclusions, mapping limits, and reproduction commands. The Chinese research corpus remains quarantined; the older Deepparse ZIP was unavailable.

The additional real-data material lives in `data/expanded/`: original unlabeled web strings, separate teacher-labeled copies, 1,000 freshly rendered NYC records, 500 real prose blocks awaiting address-presence review, eight authored negative regressions, and the public benchmark. These additional sources have **not** been silently mixed into training.

`annotation-queue.jsonl.gz` contains 200 unlabeled web examples. It is an annotation queue, not a completed independent gold set. Teacher suggestions are in a different file to allow blind annotation.

## Reproduce on the M1 Pro

From this directory, create an isolated Python 3.11 environment:

```sh
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python prepare.py --data data/layout-independent --max-per-source 35000
.venv/bin/python check.py --data data/layout-independent
.venv/bin/python train.py --data data/layout-independent --limit 100000 --dev-limit 6000 --epochs 3 --device auto --run runs/my-run
.venv/bin/python export.py --data data/layout-independent --run runs/my-run
.venv/bin/python predict.py runs/my-run/best.pt 'Flat 4, 12 Example Road, London SW1A 1AA'
```

`auto` selects MPS when available, otherwise CPU. This session measured Linux CPU training only; MPS correctness/performance and Safari/Chromium execution still need testing on the Mac. Use `--device cpu` to establish a reference. On Linux, install the CPU PyTorch wheel from PyTorch's CPU index before the remaining requirements if CUDA dependencies are unwanted.

Use a new `--run` directory for each experiment. A checkpoint retains weights, optimizer state, RNG state, configuration and provenance; `best.pt` is selected by generated development exact-span accuracy. This selection criterion does not certify real-input accuracy. `--init runs/previous/best.pt --lr 0.0005` initializes from previous weights with a **fresh AdamW optimizer**, not an exact resumption of optimizer/RNG state. Parent checkpoint hashes and source snapshots are recorded.

The optional `--gap-features` input encoding preserves whether each token followed whitespace or a line break. It prepends one existing space/newline byte to that token's bytes; source spans remain unchanged and no parameters are added. The original limit is still 64 raw UTF-8 bytes per token (up to 65 encoded bytes with the cue). Checkpoints record the encoding and Python/JavaScript inference use the same setting. This is an experimental switch, not an assumed improvement.

For fixed-set diagnostics and paired changes against an earlier diagnosed run:

```sh
.venv/bin/python diagnose.py --run runs/previous
.venv/bin/python diagnose.py --run runs/my-run --compare runs/previous
```

To prepare the additional staging material:

```sh
.venv/bin/python prepare.py --data data/expanded --extras-only
.venv/bin/python teacher.py --data data/expanded --library /path/to/libpostal.so --resources /path/to/libpostal-data
```

On macOS, provide the corresponding `.dylib`. The teacher used here is libpostal revision `25099c506612b34b23b1bfe286ca6321fcf06f35` with its default v1.0.0 resource archives, **not** Senzing's v1.2 trained model. Archive URLs and hashes are in `data/expanded/teacher-labeling.json`. Its Linux build and downloaded resources are currently under `/tmp/address-libpostal*`; rebuild or retain them before relying on temporary storage. Compilation used `./bootstrap.sh`, `./configure --prefix=... --datadir=... --disable-data-download`, `make -j4`, and `make install`.

For the Wasm check, install `onnxruntime-web@1.29.0` into a separate temporary Node directory, then pass that directory:

```sh
node wasm-check.mjs runs/my-run/export /path/to/runtime-install
```

The harness runs the float model in the web runtime under Node. It is an early compatibility check, not a finished browser package, browser timing study, or small custom runtime. `weights-int8.npz` measures compressed weight storage; it is dequantized for the accuracy comparison and does not establish integer-inference speed.

## Evaluation boundaries

- Generated development: exact ordered labels and raw spans, including controlled variants. Training and development have disjoint recorded groups and normalized strings.
- Public Senzing benchmark: 12,868 records; casefold/NFKC/whitespace-normalized field-map agreement. This differs from exact span accuracy. The public benchmark is now diagnostic development evidence, not an untouched final test.
- Real web data: unlabeled or unverified teacher labels. Agreement with libpostal is not independent correctness.
- Negative and ambiguous inputs: no calibrated model behavior yet. The prediction CLI returns `status: unassessed` rather than pretending that every field assignment proves an address is present.

The importer preserves libpostal's 20 field types. Rare fields and countries have very few examples. Archive prefixes are bounded samples, not globally representative samples; source IDs are unavailable for some upstream tagged rows, so duplicate controls cannot prove all underlying geographic overlap is absent. Raw-data redistribution must preserve upstream provenance and applicable data terms.

The latest aggregate research candidate is `runs/multisource-100k/best.pt`: 85.90% generated development exact spans, 77.79% public field-map agreement, and 87.53% on the supplementary source-derived holdout. It improves public agreement but regresses on some countries and the old generated development set; `runs/continuation-100k/best.pt` remains the comparison checkpoint. See the [source-quality report](address-source-quality-audit.md) for results and limitations. The earlier `gaps-100k` experiment regressed and is not the default; the [accuracy-improvement report](address-accuracy-improvements.md) and [first run report](address-training-results.md) preserve previous campaigns.

To compare either checkpoint on the supplementary set:

```sh
.venv/bin/python diagnose.py --run runs/multisource-100k --source-dev data/multisource/source-dev.jsonl.gz
```

`--source-dev` evaluates only that set and writes `source-dev.json`. Ordinary diagnostics verify the checkpoint's training-data hash before reporting training-sample accuracy.
