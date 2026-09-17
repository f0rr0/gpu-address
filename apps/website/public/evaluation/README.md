# US/UK external-source benchmark — 17 September 2026

This is an author-run evaluation on newly collected official address records.
Labels come from source columns, not predictions from gpu-postal, libpostal,
Senzing, Deepparse or an LLM. It is not an independent third-party certification.

## Primary results: full source-field addresses

| Parser | US (1,020) | UK sample (500) |
| --- | ---: | ---: |
| gpu-postal int5 experimental.2 | 1,010 / 1,020 — 99.0% | 465 / 500 — 93.0% |
| libpostal default | 1,015 / 1,020 — 99.5% | 472 / 500 — 94.4% |
| libpostal Senzing v1.2 | 1,010 / 1,020 — 99.0% | 477 / 500 — 95.4% |
| Deepparse 0.10.0 BPEmb + attention | 1,005 / 1,020 — 98.5% | 31 / 500 — 6.2% |

These are whole-address exact matches. A single wrong field fails an address.
They do not establish general parity, superiority, or accuracy on customer traffic.
Deepparse's UK result reproduces on these street/town/postcode inputs; its
published token/tag accuracy measures something different. Its other models and
fine-tuned versions were not tested. See field scores and errors, not just bars.

## Sources and scope

- US: [FDIC locations API](https://api.fdic.gov/banks/docs/), 78,075 source records
  in the September 11, 2026 index, retrieved September 17. Sample: 20 bank branches
  per state and DC. Source fields: ADDRESS + ADDRESS2, CITY, STALP, ZIP.
- England: [Department for Education GIAS](https://get-information-schools.service.gov.uk/Downloads),
  September 17, 2026 extract. Sample: 50 open schools/colleges per English region.
  Source fields: Street, Town, Postcode. Records with Locality or Address3 are
  excluded because those lines cannot be reliably mapped into common parser
  labels without additional annotation. This selects a simpler address subset.
- Northern Ireland: [Libraries NI 2026](https://admin.opendatani.gov.uk/dataset/library-locations-ni).
  Sample: 50 libraries. Source fields: Number + Street, Town, Postcode.

The UK sample is 450 England institutions and 50 Northern Ireland libraries.
**No Scottish or Welsh evaluation is claimed.** Downloaded Scottish and Welsh
files had untyped address lines and were not used. No claims cover residential,
delivery, handwritten, naturally noisy or multilingual address traffic.

UK public-sector source data is reused with attribution under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
FDIC records are US federal public data. Source provenance and exact SHA-256
hashes appear in `manifest.json`. No source contact names, phone numbers or
email addresses are included in the published sample.

## Selection, rendering and leakage checks

Within each stratum, rank eligible source IDs by SHA-256 of
`external-us-uk-v1-20260917` + source ID and select the required count.
Deduplicate normalized street+town or street+postcode within the candidate pool.
Exclude matches on either key against released-model training records and prior
Senzing/GeoSearch evaluations. The exclusion log records 385 such matches in the
candidate pool, not necessarily in the eventual sample. Matching uses NFKC,
casefold and removal of non-word characters. Fuzzy/near-duplicate, institution
and competitor-training overlap remain unknown.

All 1,520 selected source entities and their labels were frozen before inference.
The original protocol included only a missing-postcode variant. The user requested
broader robustness tests after three parsers had run, but before predictions or
scores were inspected. `protocol-v1.json` preserves that initial freeze; version 2
keeps the same source entities and adds deterministic variants. No selection,
labels, model weights or thresholds were changed in response to scores.

Inputs are comma-separated renderings of the source's core address fields, not
unaltered free-text user submissions. Organization names and optional UK counties
are omitted. US full inputs have street/city/state/ZIP; UK full inputs have
street/town/postcode. County is not required. Source errors are possible; records
have not received independent human address-by-address adjudication.

## Scoring

All parsers receive identical text without country hints. Fine-grained street
labels (premise, house number, road, unit, orientation) map into street_address.
Municipality maps to city; Province maps to state. Other geographic labels remain
separate and extra predictions fail. No parser output is discarded to rescue a
score. The seven-field map is documented in `packages/training/schema.py`.

Per-field NFKC/casefold token multisets ignore case, commas and whitespace but
retain other punctuation and token multiplicities. Within-field token order is
ignored. Whole-address accuracy requires identical field dictionaries. This
does not measure native fine-grained label accuracy or exact character spans.

Field F1 is micro-averaged exact-value field extraction: a wrong value contributes
one false positive and one false negative; a spurious field contributes a false
positive. Gold-present field exact-match counts are also available. `results.json`
contains these scores and 95% Wilson intervals for whole-address matches.
Intervals summarize each cohort's sample variability; they do not account for
source bias or correlated institutions. Equal strata are not population weights.

## Robustness

Every original is tested under six separate deterministic changes:

1. Remove postcode.
2. Remove city/town.
3. Remove street (retain US city/state/ZIP or UK town/postcode).
4. Lowercase all values.
5. Remove commas, joining fields with spaces.
6. Join fields with line breaks.

The same entities appear in every test. **10,640 test inputs are 1,520 source
entities, not 10,640 independent addresses.** Never pool variants into a headline
accuracy. These tests isolate format/missing-field sensitivity; they do not
measure typos, swapped components, unit extraction or natural partial-input
frequency. All results, including regressions, appear in `results.json`.

## Artifacts and reproduction

- `inputs.json`: source IDs, country/region, cohort, text and source-derived spans.
- `manifest.json`: sampling protocol, source download URLs/hashes and model hash.
- `gpu.json`, `libpostal.json`, `senzing.json`, `deepparse.json`: every prediction.
- `results.json`: exact numerators/denominators, confidence intervals, field scores
  and prediction hashes.
- `execution.json`: verified comparator asset hashes and model versions.
- `browser-parity.json`: Chromium WebGPU predictions and UTF-16 spans match the
  Python int5 reconstruction on **all 10,640 inputs**, using the released model.

From the repository root, independently verify published scores with Python's
standard library (no model, training data or PyTorch required):

```sh
python3 packages/training/scripts/verify_external_benchmark.py --directory evaluation
```

Run the browser parity check against the published Python outputs:

```sh
npm run build --workspace gpu-postal
python3 -m http.server 8765 --bind 127.0.0.1
# Open http://127.0.0.1:8765/packages/core/test/external-benchmark.html?dataset=evaluation
```

The preparation/inference harness is
`packages/training/scripts/external_benchmark.py`. `prepare` requires the frozen
source snapshots and original training-overlap database; source URLs and hashes
are in the manifest. Mutable upstream sources may no longer reproduce those
hashes: preserve the snapshots and use the published inputs to reproduce scoring.
`expand` adds protocol v2 variants before inference. Rerunning a frozen preparation
is rejected to prevent silent benchmark replacement.

For inference, place `manifest.json` in
`data/independent-us-uk-20260917/`, use the released checkpoint under `runs/` for
Python gpu inference, and the pinned comparator installations under
`data/competitor-tools-20260916/` described by `execution.json`. Then:

```sh
uv run python packages/training/scripts/external_benchmark.py gpu
uv run python packages/training/scripts/external_benchmark.py libpostal
uv run python packages/training/scripts/external_benchmark.py senzing
PYTHONPATH=packages data/competitor-tools-20260916/venv/bin/python packages/training/scripts/external_benchmark.py deep
uv run python packages/training/scripts/external_benchmark.py report
```

No model was trained or tuned for this evaluation. The original Senzing diagnostic
remains available at `/benchmarks.json` for provenance, but is no longer the
website's primary accuracy chart.
