# Public-address benchmark — protocol 4

Author-run comparison of the released gpu-postal int5 experimental.2 weights,
libpostal default, Senzing v1.2, and Deepparse 0.10.0 BPEmb + attention.
This measures agreement with registry fields, not nationwide parsing accuracy or
address validity. No model was trained, tuned or selected using these results.

## Sample

- US: 842 addresses across 40 states from the USDOT National Address Database
  (NAD), including subaddresses. Coverage and counts vary by state.
- UK: 200 Companies House registered offices, 50 each from England, Scotland,
  Wales and Northern Ireland. 49 have a source county; 151 do not.
- The county groups contain different records. Their difference is descriptive,
  not a causal estimate of adding or removing a county.
- These are structured records rendered with comma separators, not natural user
  traffic. UK registered offices do not establish residential performance.

The NAD candidate pool uses 6,000 unique object IDs sampled with Python's
`random.Random('broader-v3-20260917')` from `range(1,102476026)`; 5,733 returned
records. Up to 25 eligible, distinct addresses per available state were chosen
by SHA-256(seed + source ID). Postal city comes from `Post_City`, never inferred
from an administrative municipality. Missing/placeholder fields and malformed
ZIPs are excluded. Building, floor, unit and room values are retained; the
aggregate subaddress is used only when those fields are absent.

Companies House candidates are the 100 lowest SHA-256(seed + company ID) ranks
per postcode-derived nation from the September 1, 2026 full monthly CSV snapshot.
After eligibility and overlap checks, take the first 50 distinct addresses per
nation. Cross-border postcode areas SY, CH, HR and TD were excluded rather than
assigned to a guessed nation. This is not population weighting. Registry default
addresses, counties entered as towns, exact duplicate lines/towns and postcodes
repeated in address lines are excluded. AddressLine1, AddressLine2 and POBox are
retained, including premises, units and dependent localities. CareOf and country
fields are omitted. County is retained when supplied. Source-field mistakes can
remain: the target labels are registry fields, not independently adjudicated
human annotations.

Normalized street+town OR street+postcode matches against released-model training,
the earlier Senzing/GeoSearch evaluations and our earlier institutional benchmark
are excluded. Near matches and competitor training overlap are unknown. NAD can
share upstream sources with OpenAddresses; a new download is not proof that an
address was unseen by a competitor. Hashes and exclusions are in `manifest.json`.

FSA data was inspected but not scored: its generic address lines do not reliably
identify towns/counties. Independent annotation is needed before inclusion.

## Protocol history

Protocol 3 retained the same 1,042 entities but omitted optional UK counties.
After its results were inspected, protocol 4 restored every source-supplied
county. No selected entity was added, removed or replaced, and no source value
was corrected based on a prediction. Protocol 3's inputs, scores, predictions and
manifest remain at `/evaluation-v3/`. The initial source-quality preflight is
retained locally in `data/broader-benchmark-20260917/preflight-before-inference/`.
The older bank/school/library diagnostic remains at `/evaluation/`.

## Scoring

Every parser is projected onto the same four fields:

- Address block: street/building/unit plus locality.
- Town/city.
- Region: state plus district; includes source-provided UK counties.
- Postcode.

Unexpected country fields remain errors; they are not discarded. This projection
does not test fine-grained locality/district extraction. Fine-grained model
outputs are preserved in the prediction files.

Each field is compared as an exact multiset of NFKC-normalized, case-folded tokens.
Commas and whitespace are ignored; all other punctuation and token multiplicity
remain significant. A wrong field contributes both a false positive and a false
negative. Missing fields contribute false negatives; extra fields contribute
false positives. Exact-field micro F1 = 2 TP / (2 TP + FP + FN). It is not token
accuracy and is not interchangeable with Deepparse's published tag accuracy.
Whole-address exact match requires all fields to match with no extras. Its 95%
Wilson intervals describe this selected sample, not national performance.

## Reproduce and verify

From the repository root, using Python's standard library:

```sh
python3 packages/training/scripts/verify_external_benchmark.py
python3 packages/training/scripts/verify_external_benchmark.py --directory evaluation-v3
python3 packages/training/scripts/verify_external_benchmark.py --directory evaluation
```

This reconstructs input text and gold components from the published source fields,
checks prediction hashes and independently recomputes exact-match, aggregate F1
and individual-field scores without importing the training scorer.

For inference, the frozen inputs are sufficient; raw source downloads and training
data are not needed. The pinned comparator installations and released checkpoint
are required, as described by `execution.json` and
`packages/training/scripts/website_benchmark.py`. From the repository root:

```sh
uv run python packages/training/scripts/broader_benchmark.py gpu
uv run python packages/training/scripts/broader_benchmark.py libpostal
uv run python packages/training/scripts/broader_benchmark.py senzing
PYTHONPATH=packages data/competitor-tools-20260916/venv/bin/python packages/training/scripts/broader_benchmark.py deep
uv run python packages/training/scripts/broader_benchmark.py report
```

`prepare-baseline` reconstructs v3 selection from the raw snapshots and original
training-overlap database; it also rejects replacing a frozen protocol.

Raw files are under `data/broader-benchmark-20260917/`; `collect` downloads or
checks the candidate source snapshots. Mutable APIs may return changed data;
use the frozen published inputs for exact reproduction. `prepare` derives v4
from the retained v3 inputs and rejects replacing an existing frozen protocol.

Browser verification:

```sh
npm run build --workspace gpu-postal
python3 -m http.server 8765 --bind 127.0.0.1
# Open http://127.0.0.1:8765/packages/core/test/external-benchmark.html
```

All 1,042 released-WebGPU predictions and text spans matched the Python int5
reconstruction. See `browser-parity.json`. `execution.json` records verified
comparator asset hashes and execution code hashes.

## Sources and reuse

- [USDOT NAD](https://www.transportation.gov/gis/national-address-database).
  [Official disclaimer and reuse terms](https://www.transportation.gov/mission/open/gis/national-address-database/national-address-database-nad-disclaimer).
  Source query URLs and response hashes are recorded in the manifest.
- [Companies House free monthly data](https://download.companieshouse.gov.uk/en_output.html).
  [Companies House explanation of public-register reuse](https://forum.companieshouse.gov.uk/t/is-data-provided-under-the-ocs/4513).
  Public registered-office address fields are included; the separate CompanyName
  column and officer records are not included. Source address fields can contain
  organization or care-of names. Do not treat third-party source data as MIT code.

## US-only usaddress supplement

usaddress 0.5.16 was added after the original four-parser evaluation, using exactly
the same 842 frozen US inputs. It is not evaluated on the UK cohort. No fitting,
input edits, or sample selection were performed. Its training overlap is unknown.

The default `usaddress.parse` output maps PlaceName to city, StateName to state,
ZipCode to postcode, and street/building/recipient/box tokens to the address block.
NotAddress remains an unrecognized field, so it cannot silently earn credit.
Every returned token is retained; tokenizer omissions count under the existing
exact-field scoring rule. Original labels are preserved in `usaddress.json`.

`usaddress-results.json` contains scores, dependency versions, input and prediction
hashes, the full label mapping, and the model file hash. Its 133,768-byte
`usaddr.crfsuite` compresses to 53,853 bytes with Brotli quality 5. Python,
CRFsuite and feature-extraction code are excluded, as runtime code is excluded
for every parser. The gpu-postal model measures 78,919 bytes under that setting.
This compares model assets for US parsing, not equivalent output granularity or
total application download size.

Reproduce from the repository root:

```sh
uv run --with usaddress==0.5.16 --with brotli==1.2.0 python packages/training/scripts/usaddress_benchmark.py
uv run python packages/training/scripts/verify_external_benchmark.py --directory evaluation-v4
```
