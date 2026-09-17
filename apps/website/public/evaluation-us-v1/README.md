# US-only release evidence — experimental.3

Current int5 model: `06a212f708a52c32e099c15e384e3bd149885c01d06c4b00343cc3b7ad894b60`.
Selected epoch 20 of the 26-epoch US-only run. This release keeps the seven-field
API and publishes the candidate's order flexibility alongside its building and
PO-box limitations. It is not a claim of uniform superiority over usaddress.

## NAD: conventional full addresses

`nad-inputs.json` contains the unchanged 842 US inputs from
[/evaluation-v4/README.md](/evaluation-v4/README.md): 40 states, 118 subaddresses,
structured NAD fields rendered as addresses. `nad-gpu.json` contains fresh
experimental.3 predictions. Comparator outputs remain under `/evaluation-v4/`:
`usaddress.json`, `libpostal.json`, `senzing.json`, `deepparse.json`.
`results.json` reports current whole-address matches, exact-field F1 and per-field
F1. Source-field reconstruction and comparator provenance remain in v4.

All parsers use the same four-field projection: locality joins street, district
joins state. Compare NFKC/casefold token multisets, ignoring commas and whitespace
only. Extra fields and repeated tokens count. Wilson intervals describe this
selected sample, not US population accuracy.

Earlier training-overlap exclusions covered the previous release's corpus, not
the new 3-million-row US addition. Overlap with the expanded corpus and competitor
training is unknown. This is a previously inspected diagnostic, not newly blind
data. NAD can share upstream sources with OpenAddresses.

## Partial, shuffled and difficult addresses

`diagnostic-predictions.json` retains every text, label, parent, source URL and both
parsers' predictions from the 1,181-case frozen suite. The primary institutional
suite derives from only 20 addresses: Mayo Clinic, Queens Public Library,
National Park Service, MD Anderson and NASA public contact information. The
official source URL is recorded with each parent. The 100-case historical US50
sample is separate. Retain `us50-LICENSE.md` when redistributing that material.

Institutional labels were authored before pilot inference. Reordered variants
move intact fields; partial variants omit fields; typo variants deterministically
transpose letters. Building-prefix variants add the source's organization or
building heading. The suite was inspected during development. Variants are
correlated; do not pool them or attach independent-observation intervals.

This scorer preserves all seven fields, unlike the NAD comparison. It requires
every field's normalized token multiset to match, ignoring case, commas and
whitespace. Building names and units belong to street_address under our schema.
usaddress's street/building/recipient/box labels map to street_address; PlaceName
to city, StateName to state and ZipCode to postcode. NotAddress remains an extra
field and is not silently discarded. See the original mapping in
`/evaluation-v4/usaddress-results.json`.

The full 680-case historical upstream US50 comparison uses the coarser scorer.
It contains 16 exact training overlaps. Entity and competitor exposure are unknown.
The displayed 100-case seven-field subset and 680-case coarse result are different
metrics and must not be interchanged.

## Size and browser

`results.json` measures both models at Brotli quality 11: gpu-postal 53,353 bytes
(Brotli), usaddress 50,189 bytes (Brotli). The latter excludes Python, CRFsuite and
feature-extraction code. gpu-postal's model plus four separately compressed
runtime modules totals 58,687 bytes (Brotli), excluding website UI and headers.

`browser-parity.json` records the 931-case private-candidate qualification.
`nad-browser-parity.json` records the additional 842-case packaged-model check.
No claim of CPU/GPU speed equivalence is made.

## Reproduce

From the repository root, with the frozen local run artifacts:

```sh
uv run --with usaddress==0.5.16 python packages/training/scripts/release_us_evidence.py
npm test
python3 -m http.server 8765 --bind 127.0.0.1
# Open /packages/core/test/external-benchmark.html in a WebGPU browser.
```

The script asserts the selected model hash, reruns NAD inference, recomputes
scores from saved diagnostic predictions, checks their frozen counts and
remeasures both model files. Hashes of the published evidence are in results.json.
The published inputs and predictions are sufficient for independent rescoring;
raw source downloads are not needed. Historical evaluations retain their own
versions and are not relabeled as this model's results.
