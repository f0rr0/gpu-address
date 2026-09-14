# Browser models for phone numbers and postal addresses

## The plan in plain language

Build **two separate browser models**: one extracts and structures phone numbers; the other splits an address into its fields. They share a training/export approach but have independent data, weights and evaluation. Neither downloads the other model.

First establish accuracy across a meaningful model-capacity range. Measure accurate candidates in the browser, then make smaller versions if the deployment benefit warrants it. Select the complete package using measured accuracy, download, startup, latency and memory. Matching gpu-lexer's parameter count is not the objective.

The model identifies which parts of the input belong to which fields. Ordinary code copies the original text/digits and applies explicit normalization rules. This prevents free-form generation from inventing a phone digit or an address component, though a model can still select the wrong span and must be tested for that.

Google libphonenumber and libpostal are development-time references and data sources. The final package must run locally without either full library, a hidden server request, or a fallback that ships the original large dependency. Phone parsing may retain the numbering metadata needed for exact normalization; those bytes count toward its budget.

**Working budgets:** the earlier **1 MiB address-package target is retired**. Address accuracy research has no fixed download-size ceiling; start around 5–10M parameters and compare roughly 20M and 50M references. Select the deployment budget from measured accuracy and browser costs. The inactive phone experiment retains its provisional 100 KiB Brotli target, subject to review when that work resumes.

This is the revised experimental design. Initial address models have now been trained; see [executed results and remaining gaps](address-training-results.md). This document defines the intended result, execution order and completion criteria. [Data and evaluation details](phone-postal-data-and-evaluation.md) preserve the generators, labeled examples, test design and reference-project lessons. [Wasm/WebGPU research](wasm-webgpu-research.md) contains the supporting backend investigation.

## 1. The final capabilities

### 1.1 Phone parsing and extraction are separate contracts

**Parse:** given one candidate string and an optional default dialing region, return its structured phone representation or an explicit failure/ambiguity result.

**Extract:** given arbitrary text and an optional default dialing region, identify zero or more phone mentions, preserve their source spans, and parse each mention. This includes rejecting distracting numeric content.

Google distinguishes parsing, finding numbers, possibility checks, validity checks, formatting, and additional geographic/carrier lookups. Do not collapse these into one success flag. In particular, `findNumbers` has acceptance policies including `POSSIBLE`, `VALID`, `STRICT_GROUPING`, and `EXACT_GROUPING`; its result is not simply every substring that `parse` accepts.[^1][^2]

Proposed browser-facing representation:

```text
input: { text, defaultRegion?: ISO region, mode: parse | extract }

result:
  matches: [
    {
      start, end, raw,
      countryCallingCode: string | null,
      nationalSignificantNumber: string | null,
      extension: string | null,
      e164: string | null,
      regionCandidates: string[],
      countryCodeSource: explicit_plus | international_prefix |
                         default_region | other | unresolved,
      status: parsed | ambiguous | invalid | unsupported,
      possible: boolean | null,
      valid: boolean | null,
      confidence
    }
  ]
  status: ok | no_match | ambiguous | unsupported
```

This is a proposed API, not Google's exact proto. A compatibility adapter should preserve the original proto and errors in research records. Google's proto includes country code, numeric national number, extension, leading-zero metadata, and optional raw-input/provenance fields. For the browser contract, use digit strings and the library's national-significant-number accessor: reading its numeric national-number field alone loses significant leading zeros.[^3]

**Concrete task example:** `Call +41 44 668 18 00 ext. 023` should yield a mention with calling code `41`, national significant number `446681800`, extension `023`, and base E.164 value `+41446681800`. The extension is separate from E.164. This is a proposed fixture, not a newly executed oracle result.

**Required distinctions:**

- Calling code is not a unique country identifier: `+1` is shared; non-geographic calling codes also exist. Country identification may remain unresolved.
- A national number without a default region may be inherently ambiguous. Do not train a model to guess the most frequent country and call it correctness.
- Possible length, validity under a numbering-plan snapshot, and actual reachability are different facts. Reachability is outside this offline task.
- `00` is not a universal replacement for `+`. Italy's significant leading zero must not be treated as a removable trunk prefix. Regional transformations need an explicit policy.[^4]

The research record may retain number type and other teacher outputs, but these are not mandatory learned outputs. Display formatting, short/emergency numbers, carrier lookup, and geocoding require separate scope decisions. The target is extraction and structured parsing, not the whole library surface.

### 1.2 Address field parsing, with explicit abstention

**Problem:** given a string intended to represent one postal address, possibly incomplete or malformed, return the visible address components and their source spans, or indicate that the input is non-address, ambiguous, or outside supported coverage.

**Initial boundary:** parse an address candidate, not arbitrary document-wide address discovery. Finding multiple addresses inside an email is another task and requires independently labeled mention boundaries. Surrounding delivery instructions can be a later, explicitly measured extension.

```text
input: { text, countryHint?: string, languageHint?: string }

result:
  status: parsed | partial | ambiguous | not_address | unsupported
  components: [{ label, start, end, raw, confidence }]
  unassignedSpans: [{ start, end, raw }]
  alternatives?: [component sequence]
```

Use an ordered component list, not only a dictionary: repeated fields should not overwrite each other. Raw extraction must remain separate from optional normalization. For example, extracting `St` as part of a road does not require choosing whether it expands to “Street” or “Saint.” Missing components remain missing.

Proposed example: `Flat 4, 12 Example Road, London SW1A 1AA` yields unit, house number, road, city, and postcode. This illustrates segmentation only; the string is not a claim about an existing or deliverable address.

Retain libpostal's label vocabulary in the dataset:

```text
house, house_number, road, unit, level, staircase, entrance, po_box,
postcode, suburb, city_district, city, island, state_district, state,
country_region, country, world_region, category, near
```

`house` covers building/venue names; it is not the house number. `category` and `near` concern geographic search queries and can be excluded from a postal-only public contract while remaining recognizable out-of-scope cases.[^5]

Add an `O`/unassigned label and an input-status target for this experiment. Libpostal's field predictions alone are not ground truth that arbitrary prose is an address. Validity, deliverability, geocoding, and reconstructing omitted geographic facts are outside the parsing contract.

There is also an important baseline detail in the inspected source: libpostal explicitly clears its language/country parameters before filling parser context. Supplying a country hint to a new student would therefore add information the inspected baseline does not use. Report no-hint parity and hint-assisted performance separately.[^6]

## 2. One execution path

### Step 1 — Freeze the target and the test

Use the output contracts below and write a coverage manifest listing supported countries/scripts, phone formats and maximum input lengths. The first data audit can use a representative international cohort; the final model is evaluated on every country/script it claims to support. A country-specific build is an explicit alternative, not a substitute for the international target.

Keep parsing and extraction separate in the phone score. In candidate parsing, a parseable number can be returned even if metadata says it is invalid. For text extraction, use Google's `VALID` matcher policy as the initial compatibility target. Preserve independently annotated human-meaning disagreements in a separate evaluation set; do not change the primary definition between runs to favor a model.

Measure the current libraries on this exact contract and supported coverage. Use the smallest capable libphonenumber-js configuration as the practical phone baseline, not only Google's broad bundle.[^14] The references establish the quality and deployment cost to improve upon; they are not extra models to train.

Create the locked test before tuning. Seed it with independently annotated real inputs, negatives and ambiguities; keep known upstream regressions in a separate development suite. Record denominators and confidence intervals. Section 5 defines provisional success targets.

### Step 2 — Build and audit the labeled data

Follow the [phone and address generation recipes](phone-postal-data-and-evaluation.md). Start from known structured values, render varied inputs and retain field spans. Mix ordinary examples with rare formats, incomplete inputs and confusing numeric/prose negatives.

Audit a few hundred representative rows before scaling. Then run a roughly 20,000-row pipeline check and grow to 100,000 and 500,000 examples as learning curves justify it. These are checkpoints, not final corpus limits. Grow unique source records and linguistic/format coverage, not just repeated variations of the same examples. No unverified teacher prediction becomes unquestioned gold.

### Step 3 — Train an accurate reference model

Start with a character-aware sequence tagger: it reads local spelling and surrounding context, labels fields, and uses a small sequence decoder to keep labels coherent. A compact bidirectional contextual layer plus a linear-chain CRF is the initial model family; byte/character features must preserve coverage of the supported scripts. No general-purpose text generator or large word dictionary is required by this design.

For addresses, start the new accuracy reference around **5–10 million parameters**, with comparisons around **20 million and 50 million**. Retain the existing 615k model as a baseline. These are experimental anchors, not a final-size ceiling. Give each configuration sufficient training and compare both matched budgets and convergence on consistent supervision. Train on reliable labels and inspect field, data and decoder errors alongside scaling. See the [updated address research plan](address-next-research-plan.md).

### Step 4 — Export an early candidate to the browser

Do this after the first functioning model, before spending effort on a long accuracy campaign. Use a minimal automated inference harness, not a product demo. Verify that the chosen operations export, the browser returns the same fields, Unicode offsets survive and total size/memory are measurable.

Use a CPU path first, with Wasm as the initial deployment candidate. A generic inference runtime can verify export early, but its actual download cost counts; it is not automatically the final runtime. Profile before committing to a dedicated small kernel. Keep a simple numerical reference for cross-checking.

### Step 5 — Measure deployment tradeoffs and compress where useful

Measure the accurate reference and an int8 version as browser candidates. A larger model can be the final candidate if its measured costs suit the application. Train a smaller student only when reduced download, startup, memory or latency is worth investigating; use the same ground-truth labels and stronger-model supervision where it helps.

Try smaller widths or fewer layers one change at a time. Compare float and quantized versions to separate capacity loss from quantization loss. Use quantization-aware training if measured int8 errors warrant it. Lower-bit weights are a later option, not a starting requirement.

Keep an accuracy-versus-complete-bytes table for every serious candidate. Do not choose a tiny checkpoint because its synthetic token score looks good when its complete phone/address results are worse.

### Step 6 — Qualify and package the final model

Repeat finalists across three to five seeds, calibrate on development data, then run the locked evaluation through the packaged browser API. Test Safari and Chromium on the M1 Pro, including warm calls, first use, negative inputs and batches. Profile WebGPU only if CPU latency or batch throughput creates a reason to add it.

Completion means an installable local package, documented coverage, versioned weights and any metadata, reproducible export, and a report showing accuracy, complete bytes, latency and memory. A good Python checkpoint is an intermediate result.

## 3. Model boundaries and deployment decisions

**Phone model:** identify mentions and raw field roles. A small deterministic normalizer uses the declared region and versioned parsing metadata to handle prefixes, significant zeros, extensions and supported digit/letter mappings. Each transformed digit must have an auditable origin in the input or an explicit numbering rule. Missing digits or country context are not guessed.

Inspect the minimum normalization metadata needed before relying on size savings. Retaining the entire existing parser behind the network would not meet the intended replacement goal. Possibility/validity checks are optional explicit metadata-backed functionality; leave their fields unknown when that functionality is not included. Do not claim validation compatibility for a parsing-only artifact.

**Address model:** assign the existing field labels and unassigned spans, then group them into an ordered result. Country hints are optional inputs, never hidden training information. The default target is one international model; investigate per-country variants only if the measured size/accuracy curve calls for them. Missing cities/postcodes remain missing. Confidence does not guarantee detection of every unsupported input.

**Minimum comparison set:** existing library, accurate float reference, and quantized shipping candidate. Add a compact rule-based or linear-CRF control only when it answers a specific question about an observed error or size cost. Do not run an entire architecture/backend grid before obtaining one working pipeline.

**Browser delivery:** ship each task independently. Count weights, normalization metadata, tokenizer, decoder, Wasm/JS glue and all inference-runtime assets required after a clean load. Exported results must match the tested candidate; runtime parity failures block release. Full baseline-library fallback is excluded from the model's headline results.

For short inputs, start with single-threaded CPU inference and measure end-to-end cost. Wasm can run a neural model without WebGPU; the preferred engine is a measurement result, not a product requirement.[^17] The QIP study and its separate SIMD experiment support this distinction, as detailed in [the backend research](wasm-webgpu-research.md).

## 4. M1 Pro with 16 GB RAM

These proposed small-student experiments are plausible on the machine. PyTorch supports the `mps` device for Apple GPU training; that does not guarantee that every chosen operation or training configuration is supported or faster than CPU.[^16] Check actual device availability, train-step correctness, peak memory, and CPU/MPS parity before a longer run.

The larger risks are materializing training data, retaining full libpostal resources alongside training, and spawning workers that duplicate memory. Generate or read shards incrementally, keep worker counts low initially, and separate bulk teacher labeling from student training. Cache oracle results by input, region/policy, and artifact hash.

For addresses, take a stratified sample from existing tagged data or generate from selected source extracts. Do not begin by rebuilding the full worldwide libpostal pipeline or downloading its entire training corpus. A country-specific slice from a compressed global archive may still require substantial scanning/download work; inspect storage and streaming access before choosing that route.

Rent compute only when measurements show a concrete need: expensive global preprocessing, teacher throughput, larger models, or multiple training runs. No credible wall-clock training estimate is available until the first measured pilot. M5 timing figures from QIP must not be reused as M1 Pro forecasts.

## 5. What counts as success

The values below are **proposed experiment targets** that make “high accuracy” and “reasonable size” testable. They are not current results. Freeze or revise them explicitly before candidate selection, and publish shortfalls rather than changing denominators.

| Measurement | Phone target | Address target |
| --- | --- | --- |
| Complete compressed package | Provisional 100 KiB Brotli | No initial ceiling; select from measured accuracy and browser costs |
| Exact parsing of independently labeled, supported, unambiguous inputs | At least 99.9% correct calling code + significant digits + extension | At least 99% completely correct visible field sequence |
| Text extraction | At least 99.5% exact-mention precision and 99% recall under the declared policy | Not part of the single-address contract |
| Wrong positive on independently labeled non-phone/non-address inputs | At most 0.1% of negative documents, reported separately from oracle compatibility | At most 1% of negative inputs |
| Structural and export regressions | All committed critical digit/span and runtime-parity fixtures pass | All committed critical field/span and runtime-parity fixtures pass |

These are demanding targets. Passing requires evidence on the stated population; teacher agreement or generated-data accuracy alone is insufficient. Report per-country/script/type performance with support counts and confidence intervals. Overall thresholds do not authorize advertising a poorly performing country: it needs further work or an explicit coverage limitation.

For the primary parsing score, **abstaining on a supported, resolvable example counts as a failure**. Also report accuracy among accepted results and acceptance coverage. Inherently ambiguous inputs belong in a separately annotated set where an appropriate ambiguity response is correct. Do not relabel ordinary model failures as ambiguous or unsupported.

Use independent annotation and adjudicate genuine disagreements. A small initial gold set can reveal failures, but cannot establish a 99.9% claim reliably. Expand the evaluation to a precision appropriate to the claim and require its 95% confidence bound to support the target before describing it as met. Evaluate real-input, generated stress, and oracle-compatibility sets separately.

Package size alone is not evidence of an advantage over existing libraries. In particular, the phone model must justify itself against the actual compressed cost and quality of an equivalent small deterministic baseline. For addresses, compare accurate candidates on their full browser costs before setting a release budget.

If only a larger model achieves the required accuracy, preserve and evaluate that model as a deployment candidate. Compression is optional; accurate behavior and usable browser performance determine success. Publish the measured tradeoffs and any remaining shortfalls.

## Supporting research

- [Data generation, evaluation and reference lessons](phone-postal-data-and-evaluation.md).
- [WebAssembly/WebGPU findings and measurement protocol](wasm-webgpu-research.md).

Source revisions are recorded in the data document. The initial address experiments do not yet meet the final accuracy and complete-package requirements; measured intermediate results are in the [run report](address-training-results.md).

## Sources

[^1]: Google. [libphonenumber overview](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/README.md).
[^2]: Google. [PhoneNumberUtil: parsing, finding, leniency and validation](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/java/libphonenumber/src/com/google/i18n/phonenumbers/PhoneNumberUtil.java).
[^3]: Google. [PhoneNumber protocol definition and leading-zero semantics](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/resources/phonenumber.proto).
[^4]: Google. [FAQ: regional ambiguity, prefixes, vanity numbers and validity limits](https://github.com/google/libphonenumber/blob/806ee32e8c8c74ca339d8c91a6d86ef58687c9f4/FAQ.md).
[^5]: OpenVenues. [libpostal overview, fields, training data and reported accuracy](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/README.md).
[^6]: OpenVenues. [Parser implementation, including ignored country/language hints](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/src/address_parser.c).
[^14]: catamphetamine. [libphonenumber-js: metadata subsets, custom builds and extraction](https://github.com/catamphetamine/libphonenumber-js/blob/54c020980f83a66f188013cc3bb3d6006cec09c6/README.md).
[^16]: PyTorch. [MPS backend documentation](https://docs.pytorch.org/docs/2.14/notes/mps.html).
[^17]: ONNX Runtime. [Web performance diagnosis and CPU/WebGPU guidance](https://onnxruntime.ai/docs/tutorials/web/performance-diagnosis.html).
