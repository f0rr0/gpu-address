# Phone and address data, evaluation and reference lessons

Technical companion to the [current experiment plan](phone-postal-experiments.md). The plan defines the chosen model path, size/accuracy targets and release conditions; this document supplies the detailed data recipes and the reasoning behind the checks. Initial address preparation/training is now recorded separately in [the run report](address-training-results.md); remaining controls here are requirements, not claims that final qualification has passed.

## 0. Concrete data sources and acquisition plan

Checked September 14, 2026. **There is enough public data to start both experiments.** Address parsing also has downloadable component-labeled corpora. The remaining gap is a representative, independently annotated collection of messy browser inputs. None of the sources below, alone, establishes that final accuracy.

### 0.1 What has actually been found and downloaded

| Source | Actual contents and access check | Role in our experiment |
| --- | --- | --- |
| [Web Data Commons, 2024 LocalBusiness subset](https://webdatacommons.org/structureddata/2024-12/stats/schema_org_subsets.html) | Website-extracted structured statements with source page URLs. Downloaded its 173,639-byte sample: 1,000 statements, including 33 `telephone`, 25 `streetAddress`, 18 `addressLocality`, and 24 `postalCode` statements. The 33 phone statements contain only **8 distinct raw values**. | Real website field strings for training and annotation; page URLs for acquiring surrounding text. Statements are not unique examples, and markup is weak supervision rather than verified truth. |
| [OpenStreetMap contact and address tags](https://wiki.openstreetmap.org/wiki/Key:addr:full) | `phone`, `contact:phone`, `addr:full`, and separate `addr:*` fields. Documentation and [regional PBF downloads](https://download.geofabrik.de/) checked. A bounded London Overpass sample request returned HTTP 504; no successful OSM sample acquisition in this audit. | Raw tag values supply naturally entered strings; component tags supply rendering material. Use regional files for repeatable bulk acquisition. |
| [Overture Places](https://docs.overturemaps.org/schema/reference/places/place/) | Schema and published example checked; no release extract downloaded. `phones[]`, `addresses[].freeform`, locality, postcode, region, country, and source provenance. Its [phone schema](https://docs.overturemaps.org/schema/reference/system/phone_number/) requires international `+` format, although formatting punctuation is allowed. | Additional real entities and address strings. Phone seeds are useful, but do not cover raw domestic numbers, extensions, or arbitrary surrounding prose. |
| [OpenAddresses source repository](https://github.com/openaddresses/openaddresses) | Inspected its NYC source descriptor and fetched **3 records** directly from the listed municipal ArcGIS API. Returned fields include house number, street name/type, postcode, and record ID. | Fresh structured address records from which we can render labeled strings. These are not original user pastes. |
| [libpostal training archive](https://archive.org/details/libpostal-parser-training-data-20170304) | Confirmed the pinned repository's training pointer is `20170304`; retrieved the archive manifest and a **64 KiB compressed prefix** of the UK tagged file. It decompresses into language/country/token-label rows. The complete UK file is 26,611,979 compressed bytes. | An immediately available supervised starting point. Dated, formatted training data; not a fresh independent test. |
| [Senzing libpostal data](https://github.com/Senzing/libpostal-data) | Downloaded its v1.2 public test CSV: **12,868 rows, 88 country codes**, with full address and component columns. Also fetched a 64 KiB prefix of its v1.2 tagged training archive and verified TSV content inside the tar stream. | Additional training data and a useful public regression benchmark. The test CSV has 12,692 rows marked `osm`, 140 `libpostal`, and 36 `Libpostal-bug`; it is largely OSM-derived, not an independent sample of consumer input. |
| [Deepparse address dataset](https://github.com/GRAAL-Research/deepparse-address-data) | Repository documents labeled clean/incomplete data, 100,000 clean training rows per country for 20 countries, and additional country tests. It is derived from libpostal data. Dataset archive access timed out in this audit; records not downloaded. | Optional convenient training subset. Not an independent source, and its tag vocabulary needs an explicit mapping. |
| [CMU Enron-Random subset](https://www.cs.cmu.edu/~einat/datasets.html) | Downloaded the 804,484-byte archive; found 680 message files. A simple audit found phone/fax/tel cues in 104 files and a US-style number pattern in 126. These are candidate counts, not validated mentions. Existing annotations mark personal names, not phone fields. | Secondary real prose/signature contexts and negatives. Old corporate email is a narrow distribution; it cannot establish current international coverage. |

The WDC sample is [directly downloadable](https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/LocalBusiness/LocalBusiness_sample.txt). Its full LocalBusiness release is listed as 23.23 GB across 176 files. Start with bounded portions and cap records per domain; downloading everything first would mostly increase cost and duplication.

OpenAddresses' current [API specification](https://batch.openaddresses.io/api/openapi) says processed source/cache downloads require authentication and offers requester-pays S3 access. Its GitHub descriptors also identify upstream public providers. The [NYC descriptor inspected](https://github.com/openaddresses/openaddresses/blob/c72d304378f4b416965a11b41c5689d508a45135/sources/us/ny/city_of_new_york.json) supplied a working upstream query route. The older `results.openaddresses.io` catalog is archived, so it should not be presented as current data.

### 0.2 How real unlabeled text becomes a usable example

**Phone strings:** read the original WDC telephone literal or OSM phone tag without normalizing it first. Store its source, snapshot, raw text, available country context, and whether that context could actually be supplied by an app. Run the frozen production libphonenumber version to produce canonical digits, calling code, extension, parse errors, and matcher results. Preserve rejected and ambiguous rows for review; filtering everything through successful parsing would erase exactly the cases we need to understand. A business's location is not proof of its telephone's country.

**Phone extraction from text:** isolated telephone fields do not teach mention boundaries in prose. Use WDC's source URLs to locate corresponding archived HTML in Common Crawl. Its [documented interface](https://commoncrawl.org/get-started) exposes the URL index and WARC records over HTTPS. The planned fetcher will query the matching crawl, obtain a record's file/offset/length, and request that byte range. This archived-HTML retrieval step has **not yet been exercised** in this audit.

From each HTML record, extract visible contact blocks and preserve the link between text and markup. A `tel:` link plus its displayed number can suggest a phone span and canonical value. Schema.org telephone metadata can suggest another candidate. Keep surrounding dates, opening hours, prices, IDs, and multiple contacts. A link reading “Call us” contains no visible phone number and must not become a number span. Conflicting markup, ambiguous matches, and values absent from visible text go into an audit queue, not automatic gold labels. If only the field value is available, classify it as a parsing example, not a prose-extraction example.

For coverage outside well-marked business pages, add unmarked text blocks from the same sampled domains, a small random page sample, and the secondary email corpus. Sample blocks independently of the teacher's matches. Otherwise we will never measure the teacher's misses, and empty teacher output would incorrectly become proof of a negative.

**Address strings:** OSM `addr:full`, Overture `freeform`, and website street-address literals are useful actual strings to label with libpostal and audit. However, website `streetAddress` and Overture `freeform` are not already separated into house number, road, and unit. Separate locality/postcode metadata may also be absent from the text. Store those as auxiliary evidence; do not fabricate extraction spans for invisible fields. When retrieving a visible address block from HTML, keep its original line order and separators.

**Structured address records:** preserve field identities while rendering country-appropriate strings. Here labels come from the source fields plus the renderer, so we do not need a teacher to invent the answer. Audit each provider's mapping first: the NYC descriptor, for example, maps `HOUSE_NUMBER_SUFFIX` to `unit`; that mapping needs checking against provider semantics before using it as an apartment label. Missing fields remain missing.

### 0.3 The initial acquisition sequence

1. **Establish the importer on small verified files.** Use the WDC sample, libpostal tagged prefix, Senzing public CSV, and a paginated municipal address sample. Keep the Senzing benchmark out of training. These checks are for schema, provenance, alignment, and label quality; they cannot measure model accuracy.
2. **Acquire a stratified pilot before generating millions of variants.** Proposed starting quota: roughly 1,000 distinct raw strings per task per diagnostic country, plus a separate set of real text blocks for phone extraction and rejection. Record shortages rather than filling a supposedly real-input quota with generated strings. Country/script, source, formatting, field completeness, and ambiguity determine coverage.
3. **Partition before augmentation or teacher selection.** Group repeated telephone identities, address identities, website domains/templates, and geographic/provider overlaps. WDC statements must be joined using both page URL and subject identifier: its [format notes](https://www.webdatacommons.org/structureddata/) warn that blank-node IDs are not globally unique. Libpostal, Senzing, Deepparse, OSM, and OpenAddresses are connected data families, not five independent votes or tests.
4. **Annotate a small representative audit first.** Proposed: 200 examples per task to check the annotation rules and source quality, then enlarge the real evaluation pool to support the intended confidence intervals. Include ordinary random cases as well as a separately reported difficult set. Where country/language knowledge is needed, obtain competent review rather than accepting the teacher's answer by default.
5. **Build training labels through three traceable routes.** Keep `generated-from-fields`, `existing-tagged`, and `teacher-labeled-real` provenance on every row. Correct audited real training examples. Do not use teacher-only labels as independent gold for the final accuracy claim.
6. **Scale according to measured gaps.** Generate alternate formats and contexts after the pilot reveals what is missing. Compare generated-only training with generated-plus-real training on the same frozen real evaluation set. Grow the corpus when learning curves or country/format failures justify it, rather than assuming a fixed synthetic/real ratio.

Acquisition and labeling are CPU/data work and can be done in bounded streams on the M1 Pro with 16 GB. Write compressed JSONL shards; stream PBF/TSV sources, and fetch Overture by bounded geography using its [Python client](https://docs.overturemaps.org/getting-data/overturemaps-py/). Do not materialize global corpora in RAM. Archive compressed-file prefixes are only access/schema probes: ordinary gzip does not support sampling an arbitrary compressed offset, so representative large-scale sampling requires sequential processing or suitable source partitions.

Preserve each source's data license and redistribution conditions alongside the snapshot. A repository's code license does not automatically cover all upstream address/contact data. Keep public source benchmarks separate from the new locked test, particularly when the teacher was developed against those benchmarks.

### 0.4 Reproducibility of this access audit

These are acquisition checks, not trained-model results. The small downloaded artifacts are in the temporary research directory; the URLs, measurements, and hashes below preserve the important findings in this document.

| Artifact | Snapshot or SHA-256 |
| --- | --- |
| WDC LocalBusiness sample, 2024 release | `56bb6600e85a2d46c14df52594c75e10f6790b9e9786f3bd578e683a7692f78c` |
| Senzing v1.2 public test CSV | `db58065bf7508b862e9c6ee68774312bfc7e675192e21b8ee6aa9f7aa32ed51a` |
| Senzing repository revision | `5113929832ac06619d18a4816f78a90fef8cc7a3` |
| Deepparse data repository revision | `ecb77e4ec86d82b4ed61d973adc67f5b6a7dd150` |
| OpenAddresses source repository revision | `c72d304378f4b416965a11b41c5689d508a45135` |

**Still unverified:** usable unique yield per country, successful WDC-to-archived-HTML recovery rate, broad OSM/Overture samples, and independent annotation quality. Public access and abundant records make the experiments feasible to start; they do not settle those questions.

## 1. Phone-number labeled data

### 1.1 Use two independent sources of supervision

**Structural labels from generation:** a canonical number, field identities, and a renderer's character provenance establish where content came from.

**Behavioral labels from the frozen library:** parsing results, exceptions, validity/possibility results, formatting, and matcher acceptance establish what a particular libphonenumber snapshot does.

Keep both. A deliberately inserted but invalid phone mention is still a phone mention under an intent-based extraction task, although Google's valid-number matcher may omit it. Conversely, a phone-shaped order number may be accepted by a library even though a human would not call it a phone mention. Report semantic extraction and library compatibility as different scores; never silently rewrite one label into the other.

### 1.2 Generation pipeline

1. **Pin code and production metadata.** Enumerate supported regions, number types, and example numbers. Treat example-number APIs as seeds and sanity checks, not a large diverse dataset.
2. **Generate candidate national numbers.** Sample supported branches of the metadata's number patterns, or retain valid prefixes while varying allowed subscriber positions. Bound the pattern generator and validate every output with the frozen oracle. Random digit strings of the right length are not reliably valid positives.
3. **Preserve generator coverage.** Record region, pattern branch, prefix family, number type, and length. Rejection sampling alone can overrepresent easy branches, so report attempted and accepted samples per family.
4. **Render variants.** International/national formats, locale-specific international access prefixes, separators, brackets, Unicode digits, extensions, supported vanity forms, and RFC3966 forms. Include both conventional and messy-but-accepted variants. Each format retains an alignment trace.
5. **Round-trip with the teacher.** Parse the rendered form with its declared region; compare canonical values and extensions with the source object. Quarantine unexpected differences rather than using inconsistent supervision.
6. **Embed into contexts.** Contact fragments, signatures, forms, prose, and numeric clutter, including multiple numbers. Split context-template families before creating variants.
7. **Run extraction separately.** Record mention spans for each matcher leniency and an explicit retry budget. Never let a silently exhausted matcher count as a gold negative.
8. **Add near misses and true negatives.** Dates, times, postal codes, prices, product IDs, account references, digit-heavy code, malformed extensions, missing regional context, and too-short/too-long candidates.

Google's matcher already includes exclusions for date/time and publication-page-like patterns. These deserve hard negatives and regression fixtures, not a claim that a simple digit regex is the strongest available baseline.[^9]

### 1.3 Labels worth storing

| Layer | Labels/provenance |
| --- | --- |
| Document | Input text, default region, whether region was actually supplied, positive/negative/ambiguous intent |
| Mention | UTF-16 start/end, source text, intended mention identity, teacher match spans at each policy |
| Fine-grained | Digit/letter spans for calling code, national number, extension; prefix and marker roles; punctuation/background |
| Canonical | Calling-code string, national-significant-number string, extension, teacher proto, normalized result |
| Oracle | Parse success/error type, possibility reason, validity, type, region outputs, acceptance policy |
| Generation | Canonical seed ID, formatting family, context family, mutation trace, production metadata hash |

Do not guess fine-grained span labels by searching for the canonical digits in the raw string: repeated digits, removed prefixes, letter-to-digit mappings, and split digit groups make that unreliable. An instrumented renderer or traceable normalization pass should retain the mapping. A country code inferred from `defaultRegion` has no source span.

Never delete or change a digit as “noise” while keeping the old canonical number as its label. A changed digit creates another candidate that must be relabeled, marked invalid, or rejected. The proposed system is not a phone-number autocorrector.

A minimal generated-label example, before adding oracle outputs and provenance:

```json
{
  "text": "Call +41 44 668 18 00 ext. 023",
  "defaultRegion": null,
  "mention": { "start": 5, "end": 30 },
  "fields": [
    { "role": "calling_code", "start": 6, "end": 8 },
    { "role": "national_digits", "start": 9, "end": 21 },
    { "role": "extension_digits", "start": 27, "end": 30 }
  ],
  "expected": {
    "countryCallingCode": "41",
    "nationalSignificantNumber": "446681800",
    "extension": "023"
  }
}
```

Indices are half-open UTF-16 offsets; this ASCII example also has identical byte offsets. The national field span includes presentation spaces; a renderer trace identifies its digits. These are proposed structural labels with checked offsets, not recorded results from a new libphonenumber execution. Teacher acceptance and validity would be populated separately.

### 1.4 Real data and oracle audits

Use public library regressions and intentionally collected, annotated contact fragments to challenge synthetic coverage. Keep their provenance and numeric formatting when replacing sensitive values. Anonymization that changes prefixes or length can change the correct answer.

An easily missed source trap: Google's `PhoneNumberUtilTest` states that its tests use **test metadata**, not normal metadata. Preserve those tests as implementation-contract fixtures under their original setup; do not treat their expected validity results as labels under production metadata.[^10]

Compare a Python port against the pinned Java/C++ oracle before using it for bulk generation. Record its metadata version independently. Agreement between ports sharing the same metadata is a compatibility check, not independent evidence of real-world truth.

## 2. Postal-address labeled data

### 2.1 Prefer structured-source labels over blind teacher imitation

Libpostal's documented pipeline combines OpenStreetMap/OpenAddresses records, address-format templates, geographic context, and generated variations. It also publishes tagged training files. Its repository reports a roughly 1.8 GB default model and over 100 GB of uncompressed training data; these are upstream descriptions, not measured browser artifacts. Its reported 99.45% held-out full-parse accuracy is not a universal real-input guarantee.[^5]

Use three distinct data tiers:

1. **Fresh source records rendered with provenance:** strongest control over labels, raw text, and partitioning.
2. **Existing tagged libpostal training files:** useful for an early feasibility run and broader coverage; provenance and rendering-family separation may be incomplete.
3. **Teacher-labeled messy address strings:** useful for distillation or hard-example discovery; labels are predictions and should remain marked as such.

For high-confidence structured records, a teacher disagreement does not automatically mean the source label is wrong. Audit it. Otherwise the student can never learn a legitimate correction to the teacher.

### 2.2 What the existing training format actually contains

The advertised TSV layout is language, country, and tagged address. The C reader parses token/label pairs using the **last slash**, and handles `SEP`/`FSEP` separators specially. This is richer than a plain address string with a country label. An importer must honor those conventions, including slashes inside tokens, normalization, and punctuation.[^11]

The address formatter exposes tagged rendering and ordered component transformations. Build on those mechanics or reproduce a small audited subset; do not assume applying a normal address formatter and then searching for field strings recreates correct spans.[^12]

The ready-made tagged corpus may not retain original whitespace, casing, or source IDs in a form suitable for exact browser offset tests. Treat reconstructed strings as their own inputs. Never describe their offsets as offsets into the original OSM record or real-world paste.

### 2.3 Generation pipeline

1. **Select structured geographic records.** Keep source ID, country, language/script, geographic grouping, original field mappings, and data-license provenance. Audit ambiguous mappings such as locality versus district before augmentation.
2. **Partition original records first.** Keep all variants of an address in one partition. Deduplicate overlapping source records before assigning partitions.
3. **Render legitimate local formats.** Use country-aware formatting templates and retain the identity of every emitted field. OpenCage supplies formatting templates and test cases; templates are renderers, not address validators.[^13]
4. **Add controlled variations.** Supported abbreviations, separator changes, casing, line breaks, field omissions, legitimate alternative orders, apartments/floors, and PO boxes. Keep changes plausible for the country instead of arbitrarily permuting every field.
5. **Preserve raw field content.** A typo can retain its field label, but the model should extract the typo as typed. Correcting a road name is another task.
6. **Record what was omitted.** A source city's existence does not authorize returning it when the rendered input lacks it. Invisible fields must not leak into gold extraction output.
7. **Run libpostal as a comparison teacher.** Store its component sequence and disagreement categories. Align normalized teacher components cautiously; repeated/localized tokens can make exact raw-span alignment impossible. Such rows can still supervise field content without fabricated offsets.
8. **Add non-address and partial-input sets.** Prose, names, numbers, contact fragments, product descriptions, “Springfield,” street-only inputs, building-only inputs, and geographic search queries. Human annotation defines which are partial, ambiguous, unsupported, or non-address under the chosen contract.

### 2.4 Data record

```text
id, source_id, source_snapshot, source_license
text, country_hint, language_hint, hint_was_supplied
components: [{ label, start, end, raw }]
status, allowed_alternative_parses, omitted_fields
source_country, source_script, geographic_group, normalized_address_id
render_family, augmentation_trace, base_record_id
teacher_components, teacher_model_hash, teacher_disagreements
split, annotation_provenance
```

Source country/language are always available for stratification when known, but enter the model only in experiments where equivalent hints exist at runtime. Do not accidentally feed dataset metadata unavailable to the deployed parser.

For the illustrative address above, the generated span targets are:

```json
{
  "text": "Flat 4, 12 Example Road, London SW1A 1AA",
  "components": [
    { "label": "unit", "start": 0, "end": 6 },
    { "label": "house_number", "start": 8, "end": 10 },
    { "label": "road", "start": 11, "end": 23 },
    { "label": "city", "start": 25, "end": 31 },
    { "label": "postcode", "start": 32, "end": 40 }
  ]
}
```

This is constructed segmentation supervision. The example does not label existence, deliverability, or a missing country. Internal BIO/BILOU tags can be derived from these spans after the experiment's tokenizer is fixed.

### 2.5 Geographic coverage without an unsupported global claim

Keep international parsing as the target. Start with a diagnostic cohort spanning different conventions—for example US, UK, Germany, Brazil, India, and Japan—then broaden systematically. This cohort is a research sampling proposal, not a final market restriction or a claim of language support.

The cohort should exercise house-number order, apartment and rural formats, digit/alphanumeric postcodes, diacritics, multiple scripts, and components absent from familiar Western addresses. Romanized Indian or Japanese examples do not establish native-script coverage.

Start with one international model. If scope or optional hints materially change the size/accuracy tradeoff, compare those variants on identical country test slices. Count model selection and additional assets. Unseen-country tests measure generalization; they do not automatically justify advertising that country as supported.

## 3. Partitioning and evaluation

### 3.1 Maintain four distinct collections

| Collection | Purpose | Can influence training? |
| --- | --- | --- |
| Train | Fit parameters and perform replay | Yes |
| Development | Select architecture, thresholds, losses and data changes | Yes, indirectly |
| Regression fixtures | Preserve understood behavior and invariants | Yes; report as regression coverage |
| Locked real-input test | Estimate generalization after decisions are frozen | No |

Generated out-of-template tests and geographic/prefix holdouts are additional named slices. They are not substitutes for independently labeled real inputs. Once locked results guide changes, that test version becomes development evidence. Freeze a fresh untouched test version for the next final evaluation; replacing only the failed rows would bias the test.

**Phone split axes:** canonical number identity, prefix family, formatting family, context author/source, and metadata version. Hold out every surface variant of the same canonical number together. Holding out arbitrary subscriber digits is easier than holding out an unfamiliar numbering pattern; report both.

**Address split axes:** normalized address identity, source provider, locality/geographic block, template family, and country/script. Street and locality overlap can make a record-random split look excellent through memorization. Report identity-disjoint and geographic-disjoint tests separately rather than pretending either measures everything.

### 3.2 Metrics tied to the contract

| Target | Primary measurements | Diagnostics |
| --- | --- | --- |
| Phone extraction | Exact mention precision/recall and document-level exact results | Overcapture, misses, merged mentions, numeric-negative false positives |
| Phone parsing | Exact canonical tuple: calling code + significant digits + extension | Region assumptions, prefix handling, leading-zero and digit errors |
| Phone compatibility | Exact oracle result/error under the declared metadata and leniency | Possible/valid/type agreement, metadata-update regressions |
| Address parsing | Full ordered field parse accuracy; exact field-span precision/recall | Rare fields, scripts/countries, field omissions, unit/house-number swaps |
| Address rejection | Non-address false acceptance; partial/ambiguous input behavior | False rejection of legitimate incomplete addresses |
| Both | Accuracy versus acceptance coverage, with confidence intervals | Calibration, worst supported slices, newly introduced failures |

Use source-preserving spans for extraction metrics and a separately documented normalized comparison for teacher output. Do not award full credit merely because a city or number is somewhere in the output. Also avoid letting perfect punctuation/background labels dominate a token-accuracy score.

Evaluate ambiguity explicitly: some inputs admit multiple defensible parses. Store alternatives or score correct abstention under a written annotation policy. A single teacher prediction does not remove ambiguity.

For false positives, measure on realistic negative-heavy inputs as well as balanced diagnostic sets. A synthetic 50/50 test does not estimate production precision. With zero failures in N independent cases, the approximate 95% upper failure-rate bound is 3/N; hundreds of examples cannot substantiate extremely small error-rate claims.

### 3.3 Invariants and minimum regression families

**Shared invariants:** offsets are valid and slice to the reported raw text; UTF-8/UTF-16 mappings are explicit; Unicode and separators do not corrupt fields; no invisible field is invented; oversized input is explicitly rejected or chunked under a tested policy.

**Phone families:** shared calling codes, explicit versus default country code, locale-specific international prefixes, significant zero, zero-prefixed extensions, two adjacent numbers, dates and IDs, vanity forms, Unicode digits, malformed numbers, and region conflicts. Keep extraction intent and oracle acceptance separate in expected results.

**Address families:** unit versus house number; road words that resemble names/admins; numeric road names; postcode-like house numbers; diacritics and native scripts; missing separators; PO boxes; rural/local conventions; repeated locality names; incomplete inputs; non-address prose. Neither all-empty output nor labeling every token as `road` should pass the status task.

## 4. Lessons retained from gpu-lexer and gpu-time

### 4.1 Explicit transfer from the reference projects

The following maps documented practices and failures to proposed experimental controls. These controls are part of the design; none is an already implemented or passing test for a new model.

| Reference observation | Required adaptation for these experiments |
| --- | --- |
| gpu-lexer uses a reduced teacher vocabulary, not full language semantics.[^7] | Freeze the phone/address output contract and label mapping. Score deliberately unsupported capabilities separately; never call narrower behavior full-library parity. |
| gpu-lexer separates repository/package sources.[^7] | Separate canonical numbers, address identities, source providers and rendering families before augmentation. Include stronger prefix/geographic holdouts. |
| gpu-lexer's aggregate agreement obscures uneven class/language performance.[^7] | Report macro country/field metrics, support counts and worst supported slices alongside pooled accuracy. |
| gpu-time's generated context produced the bare-hour failure.[^8] | Measure conditional distributions in the generated corpus. Vary the surrounding context of the same entity; create explicit contrast pairs and unfamiliar context families. |
| Teacher agreement missed forms absent from a teacher's capabilities.[^8] | Maintain a coverage inventory independent of oracle agreement. Teacher disagreement or silence triggers an audit, not automatic deletion. |
| Rebalancing alone failed to resolve a decoder preference.[^8] | On errors, inspect several highest-scoring sequence paths, their margins, and compiler outcomes before changing sample weights. |
| Fine-tuning introduced negative flips; averaging was not reliably safe.[^8] | Track newly broken examples as well as newly fixed ones. Compare replay or regression-aware distillation only when needed; do not average checkpoints by default. |
| Some historical evaluation labels were invalid.[^8] | Validate generated labels against their source semantics before training/evaluation. Quarantine faulty rows, version corrections and reevaluate both candidates on the corrected corpus. |
| An argmax evaluation misrepresented a Viterbi-decoded model.[^8] | Use the deployed decoder and postprocessor for primary comparisons. Keep argmax only as a named diagnostic ablation. |
| Correct public output can conceal incorrect internal roles.[^8] | Score field/role correctness and final output separately. Test counterfactual variants to expose compensating mistakes. |
| Calibration used a split called “heldout.”[^8] | Treat any threshold/calibration/selection split as development regardless of its name. The locked test cannot choose thresholds. |
| Small improvements can fall within training-seed variation.[^8] | Repeat finalists across three to five seeds with fixed corpora; compare distributions and paired failures, not the best seed. |
| Exported quantization and runtime behavior require parity checks.[^7][^8] | Evaluate actual packed weights and packaged JS/Wasm/WebGPU paths, including spans, digit strings and abstention decisions. |
| Inference reproducibility did not imply complete training reproducibility.[^8] | Retain checkpoints, parent artifacts, optimizer state, generator/data manifests and environment locks; verify export from an archived run. |

### 4.2 Controls during iteration

**Counterfactual tests must distinguish context changes from semantic changes.** For phone numbers, place the same digit sequence after a phone cue and an order-ID cue. Under semantic extraction, the expected mention status may change; under strict library-compatibility scoring, use the oracle result instead. For addresses, relocate a unit phrase among legitimate local formats and verify that the same component identities survive. Do not impose invariance when a rearrangement changes meaning.

**Inspect decoder failures before increasing model size.** For a diagnostic subset, retain the top few sequence paths and separate emission, transition, and postprocessing contributions. If the correct address segmentation is already second-best, a decoder preference or loss mismatch is a different problem from not recognizing the road at all. This diagnostic need not become part of the public runtime.

**Separate model improvements from compiler/metadata improvements.** Compare old and new weights through the same frozen postprocessor when attributing gains to training. If normalization or metadata changes too, run the corresponding old/new combinations and a full end-to-end comparison. A corrected prefix rule is valuable, but it is not evidence that the neural model improved.

**Make selection rules explicit before the final comparison.** Structural invariants and critical digit-preservation fixtures are hard requirements. Predeclare tolerances and uncertainty handling for statistical country/field metrics. A pooled gain cannot silently override a protected slice; an accepted tradeoff must appear in the result. Do not tune these rules after observing a candidate's failures.

**Archive enough to reproduce the chosen artifact.** Each run should identify code/environment, source and split manifests, production metadata or libpostal data hashes, renderer and tokenizer versions, seeds, parameters, loss settings, calibration set and thresholds, float and quantized weights, decoder/compiler versions, parent checkpoints, and evaluation results. Checkpoint averaging or distillation adds dependencies that must also be preserved. Where raw data cannot be redistributed, retain a permitted retrieval recipe and disclose the resulting reproducibility limit.

The reference records contain historical results, known failures and later updates in the same documents. Some failure descriptions and promotion summaries are not consistent across those passages. This design borrows the demonstrated failure mechanisms and methods; it does not treat every reported metric or assertion that a gate passed as a verified property of the latest artifact.

## Sources and pinned research snapshot

Sources inspected September 14, 2026. Repository revisions below identify inspected code; external model/data downloads must additionally be hashed when experiments actually run.

| Repository | Inspected revision |
| --- | --- |
| google/libphonenumber | `806ee32e8c8c74ca339d8c91a6d86ef58687c9f4` |
| openvenues/libpostal | `25099c506612b34b23b1bfe286ca6321fcf06f35` |
| catamphetamine/libphonenumber-js | `54c020980f83a66f188013cc3bb3d6006cec09c6` |
| vercel-labs/gpu-lexer | `1e514fd681e31d6b19296f985fb01d8fdc0ae74f` |
| arikchakma/gpu-time | `4c5058c55a72e38d129f490297777762ba618a33` |
| QIP, linked as royalicing/qip and redirecting to patrickgwsmith/qip | `ac753990551a76d5e5c8b831019eebc78095e530` |

[^1]: Google. [libphonenumber overview](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/README.md).
[^2]: Google. [PhoneNumberUtil: parsing, finding, leniency and validation](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/java/libphonenumber/src/com/google/i18n/phonenumbers/PhoneNumberUtil.java).
[^3]: Google. [PhoneNumber protocol definition and leading-zero semantics](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/resources/phonenumber.proto).
[^4]: Google. [FAQ: regional ambiguity, prefixes, vanity numbers and validity limits](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/FAQ.md).
[^5]: OpenVenues. [libpostal overview, fields, training data and reported accuracy](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/README.md).
[^6]: OpenVenues. [Parser implementation, including ignored country/language hints](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/src/address_parser.c).
[^7]: Vercel Labs. [gpu-lexer model card](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/MODEL_CARD.md).
[^8]: Arik Chakma. [gpu-time model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md) and [architecture](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md).
[^9]: Google. [PhoneNumberMatcher implementation](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/java/libphonenumber/src/com/google/i18n/phonenumbers/PhoneNumberMatcher.java).
[^10]: Google. [PhoneNumberUtilTest, including its test-metadata warning](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/java/libphonenumber/test/com/google/i18n/phonenumbers/PhoneNumberUtilTest.java).
[^11]: OpenVenues. [Tagged training-data reader](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/src/address_parser_io.c).
[^12]: OpenVenues. [Tagged address formatter](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/scripts/geodata/address_formatting/formatter.py), [OpenAddresses preprocessing](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/scripts/geodata/openaddresses/formatter.py), and [OSM preprocessing](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/scripts/geodata/osm/formatter.py).
[^13]: OpenCage. [Address-formatting templates and test conventions](https://github.com/OpenCageData/address-formatting).
[^14]: catamphetamine. [libphonenumber-js: metadata subsets, custom builds and extraction](https://github.com/catamphetamine/libphonenumber-js/blob/54c020980f83a66f188013cc3bb3d6006cec09c6/README.md).
[^15]: vloldik. [rlibphonenumber, Wasm demo and size-oriented feature](https://github.com/vloldik/rlibphonenumber). Unpinned secondary baseline lead; verify before experiments.
[^16]: PyTorch. [MPS backend documentation](https://docs.pytorch.org/docs/2.14/notes/mps.html).

[^17]: ONNX Runtime. [Web performance diagnosis and CPU/WebGPU guidance](https://onnxruntime.ai/docs/tutorials/web/performance-diagnosis.html).
