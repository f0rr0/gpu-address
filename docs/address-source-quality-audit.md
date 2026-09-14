# Additional address data: acquisition and quality audit

Executed September 14, 2026. We acquired and checked additional sources, then built `experiments/address-parser/data/multisource/`. This is an expanded experimental training corpus, **not a newly certified gold dataset**. Source availability is described in [the shortlist](additional-labeled-address-sources.md).

## What we acquired and used

| Source | Acquisition and audit | Decision |
| --- | --- | --- |
| Senzing v1.2 | Six 4 MiB compressed archive prefixes; 25,000 sampled rows per archive | Use filtered, capped samples from all six. Prefixes are not globally representative. |
| Deepparse worldwide | Complete first Parquet shards for 14 selected country codes; 12,000 rows sampled across each whole file | Use mapped labels after structural, duplication, conflict, and targeted contamination checks. |
| France BAN | Complete departmental CSV files for Paris, Nord, and Réunion; reservoir sample of 12,000 rows each | Use only municipality-certified records with usable core fields. |
| G-NAF | A pinned public conversion of the August 2022 data, first Parquet shard; 12,000 sampled rows | Use explicit components to render partial addresses; omit ambiguous localities. This is not the current official 2026 release. |
| Neural Chinese Address Parsing | All published train/dev/test files, label list, and English annotation guide | Preserve all 14,927 records separately. Do not train yet: schema mapping and dataset reuse terms remain unresolved. |
| Earlier Deepparse ZIP | Multiple requests to its university host timed out | Not acquired or counted as used. The newer worldwide corpus is available, but is not asserted to be an identical substitute. |

The optional Canada worldwide shard exceeded the 256 MiB per-file acquisition bound and was not retained. Other acquired archives still contribute additional Canadian examples. The 14 country partitions are Taiwan, Egypt, Liechtenstein, India, Korea, Austria, South Africa, Slovakia, Singapore, Kuwait, Trinidad and Tobago, Argentina, Guatemala, and Denmark. No claim is made that all countries or all archive shards were downloaded.

Acquired files total approximately 759 MB. URLs, retrieval dates, hashes, HTTP metadata, and sampling descriptions are retained in `acquisition.json` and `raw/*.json`. Hugging Face revisions are pinned; changing BAN downloads are frozen by content hash. G-NAF uses the [publisher's documented conversion](https://huggingface.co/datasets/dylanhogg/gnaf-2022), with its date and attribution retained.

## What the checks found

We examined **366,000 candidate rows** from the tag-compatible and structured sources. **354,511** passed structural conversion. The Chinese corpus was audited separately in its original schema.

- **Geographic contamination:** 1,370 of the 12,000 sampled worldwide Singapore rows mention Pasir Gudang. The [official city council](https://www.mbpg.gov.my/) locates it in Johor. The targeted exclusion removes 1,380 candidates across the acquired sources; it does not claim to identify every geographic error.
- **Placeholder street names:** 1,527 candidates contain a road field equal to `NINGUNO`, `SIN NOMBRE`, `UNNAMED`, or `UNKNOWN`. Excluded rather than treating placeholders as ordinary named streets.
- **Severe source skew:** all 25,000 inspected Senzing OpenAddresses-prefix records are Mexican. The source stays useful, but cannot be described as a worldwide sample.
- **Fragments dominate some country files:** only 337/12,000 sampled India records contain a house number; Taiwan has 2,145/12,000 and Egypt 751/12,000. More rows do not necessarily mean more full addresses.
- **BAN certification:** 6,300 Nord and 4,276 Réunion samples lack municipality certification. Excluded from this initial generated set; absence of certification is not proof that an address is wrong. Two additional Nord rows fail core-field checks.
- **G-NAF filtering:** 652 sampled rows are retired/aliases, and 215 lack a usable street number, road, or postcode. The remaining sample spans ACT, NSW, NT, QLD, SA, TAS, VIC, WA, and other territories.
- **Tagged source defects:** one Senzing address exceeds input limits; 43 custom-source records fail token conversion. The latter error is reported by the old importer as `Unknown label suburb`, but its branch also rejects empty tokens carrying a known label; it does not indicate a new unsupported `suburb` field.
- **Large archive compatibility:** two larger tar members use GNU binary size headers. The existing octal-only importer failed; it now uses Python's standard tar-header parser, with a regression check.

The China research corpus has valid BIO transitions in the scanned files, but its ontology is materially different: district/town/community, road versus building numbers, building sections, recipients, and redundant text. Valid BIO syntax alone does not make those labels compatible with our API.

## Label mapping decisions

Deepparse's ten tags map to house number, road, unit, suburb, city district, postcode, city, state, state district, and country. It provides no direct supervision for our remaining fields. We do not invent missing floor/building labels. Its punctuation removal and artificial CJK/Hangul spacing remain distribution limitations; the existing controlled CJK compaction is retained for eligible examples.

For BAN, the postal routing locality (`libelle_acheminement`) supplies `city`. We do not label `Paris 1er Arrondissement` wholesale as a city when the postal field says `PARIS`. Numbers and suffixes remain strings.

For G-NAF, numeric fields that arrived as floats are checked for integrality; zero values are preserved, and postcodes retain four digits. We render building/unit/level/number/road/state/postcode fields. `locality_name` is deliberately omitted because its city-versus-suburb mapping needs a consistent policy. These are labeled **partial generated inputs**, not purported full real-user strings or deliverability-validated addresses.

An additional deterministic spot review covers 96 retained originals, four per contributing stream, in `spot-review.json`. It is an agent review, not independent human annotation. It surfaced further suspicious administrative combinations, including Vienna paired with Lower Austria, and Korean building-like text included in a road field. These are recorded for deeper review, not silently “corrected” using model guesses. The corpus is suitable for a controlled experiment; semantic accuracy is still unmeasured.

## Duplication, conflicts, and evaluation protection

Before mixing new data, we excluded 8,237 existing-training duplicates, 35,752 duplicates among candidates, 17 conflicts with existing training labels, and 2,252 candidates belonging to 55 normalized inputs with conflicting candidate labels. These counts are sequential filter outcomes, not disjoint properties of the raw universe.

We excluded 1,956 candidates overlapping protected development/public inputs or recorded street keys. A supplementary source-derived holdout is created before augmentation; another 53 candidates overlap its street keys. Original development and public-benchmark files are copied **byte-for-byte unchanged**.

Per-source/country caps limit fragments, and no recorded source street group contributes more than eight selected originals in the additions. These controls filtered another 142,493 candidates. They reduce dominance and repetition without pretending a short archive prefix is representative.

Every augmentation inherits its original's split. Post-augmentation checks remove 55 evaluation-overlapping examples and 52 rows involved in 19 conflicting normalized inputs. Existing training data is preserved as the parent corpus; this campaign does not claim to have relabeled or removed every defect in that older data.

## Final corpus

| Collection | Rows |
| --- | ---: |
| Preserved previous training corpus, including variants | 200,699 |
| Additional originals after all filters | 144,857 |
| Additional examples including variants | 296,279 |
| **Combined training corpus** | **496,978** |
| Unchanged development corpus | 22,585 |
| Additional source-derived holdout | 15,976 |
| Unchanged public benchmark | 12,868 |

Selected original counts, excluding our controlled augmentations:

| Country | Before | After |
| --- | ---: | ---: |
| Taiwan | 43 | 3,226 |
| Egypt | 8 | 1,496 |
| India | 49 | 1,353 |
| Korea | 97 | 5,495 |
| Liechtenstein | 4 | 4,846 |
| Australia | 1,530 | 8,219 |
| France | 2,993 | 15,467 |
| Singapore | 104 | 5,215 |

These are imported labeled strings, including upstream-generated forms and partial addresses, **not counts of unique physical premises**. Common upstream ancestry means the sources cannot certify each other's correctness.

All 496,978 training and 22,585 development examples pass the declared tokenizer/input limits and reconstruct their labeled spans exactly. The runnable checks also cover split separation, the supplementary holdout, Unicode, mapped labels, numeric preservation, GNU tar headers, CRF parity, and a tiny learning check. These are structural guarantees, not a measured semantic label-accuracy percentage.

## Training comparison

`multisource-100k` starts from the same original checkpoint as `continuation-100k`, with the same 615,244-parameter architecture, three additional epochs, learning rate 0.0005, seed, and fixed 6,000-row development sample. Only the training corpus changes. Each run samples 100,000 rows from its respective corpus; the expanded corpus is available in full but is not all consumed in this controlled run.

The matched run completed all three epochs in 374.4 seconds of Linux CPU training-loop time. Its final epoch is also its best on the fixed generated development sample.

| Measurement | Previous continuation | Expanded-source model |
| --- | ---: | ---: |
| Fixed generated development, exact spans | 87.37% | 85.90% |
| Public benchmark, normalized field maps | 75.71% (9,743/12,868) | **77.79% (10,010/12,868)** |
| Supplementary source-derived holdout, exact spans | 61.92% (9,892/15,976) | **87.53% (13,984/15,976)** |

The public improvement is **2.07 percentage points**, or an **8.54% relative reduction in benchmark errors**. Paired predictions show 755 previously wrong cases fixed and 488 previously correct cases broken. The new-source holdout measures agreement with source labels, not independent real-input correctness. The measured native libpostal baseline remains ahead at 83.79% on the public suite.

| Public country slice | Previous correct | New correct | Total |
| --- | ---: | ---: | ---: |
| Singapore | 4 | 41 | 50 |
| Taiwan | 1 | 34 | 177 |
| Liechtenstein | 9 | 38 | 51 |
| Austria | 163 | 211 | 227 |
| Kuwait | 0 | 26 | 50 |
| India | 8 | 15 | 54 |
| Egypt | 0 | 0 | 50 |
| Korea | 3 | 2 | 52 |
| Germany | 1,818 | 1,713 | 2,020 |

Country omission falls from 966 to 598 public cases. However, unchanged Egyptian performance, poor Korean performance, and German regressions show that source volume is not enough. Coverage, natural input formatting, label definitions, and the training mixture still need work. The new checkpoint is the stronger **aggregate research candidate**, not a uniformly superior or production-qualified model. Keep `continuation-100k` for regression comparisons.

### Export verification

The model remains at 615,244 parameters. Stored-int8 weights occupy **612,787 bytes (598.42 KiB)**, excluding runtime and decoder. Float ONNX is 2,463,168 bytes, or 2,255,229 with Brotli. Stored-int8/dequantized development accuracy is 85.87% versus 85.90% float: 17 outputs change, including seven newly wrong and five newly correct. The public comparison above uses float weights.

All 29 ONNX/Wasm fixtures pass, including decoded paths and UTF-16 spans. Maximum emission differences are 0.00001144 for ONNX CPU and 0.00000954 for Wasm. Wasm ran under Node through ONNX Runtime Web; Safari/Chromium execution, Mac performance, and complete package size remain unqualified. The existing general runtime still exceeds the tiny weight download substantially.

Only one seed and one data-mixture recipe were tested. No independent human gold was added, and the inspected public benchmark remains development evidence.

## Reproduce

From `experiments/address-parser` after installing `requirements.txt`:

```sh
.venv/bin/python expand.py
.venv/bin/python expand.py --audit-only
.venv/bin/python expand.py --build-only
.venv/bin/python check.py --data data/multisource
.venv/bin/python train.py --data data/multisource --limit 100000 --dev-limit 6000 --epochs 3 --lr 0.0005 --init runs/independent-layout-100k/best.pt --run runs/multisource-reproduction
```

Use a new `--data` directory for a new corpus version; existing built corpora are protected against overwrite. Keep the cached raw files to reproduce this exact snapshot. New acquisitions from `latest` URLs may differ. `quality-audit.json`, `quarantine.jsonl.gz`, `quality-exclusions.jsonl.gz`, `spot-review.json`, and `manifest.json` retain the detailed evidence locally.
