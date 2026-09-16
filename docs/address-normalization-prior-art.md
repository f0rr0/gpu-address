# Address normalization and augmentation: prior art

Research date: 16 September 2026. Scope: US, UK, AU, NZ, CA, IE and English-language
ZA addresses; retain proper names and original-text spans. This is a research
inventory, not a change to the running [seven-country release](english-seven-release.md).
No dependencies, source datasets or upstream code were imported.

## Decision

Borrow dictionaries, typed data-generation techniques and difficult examples before
borrowing runtimes. First test **field-aware abbreviation augmentation** against a
matched training control. Keep the existing H128/WebGPU architecture. Add runtime
normalization or lexical features only if development errors justify them.

This is a broad survey of the major relevant implementation families, not a claim
to have located every address repository. Source inspection is distinguished below
from documentation-only screening. Upstream accuracy claims are not measurements
of our model, nor necessarily comparable to our exact ordered-span metric.

## Findings that change the recommendation

1. **Expansion is a many-to-many relation, not a replacement dictionary.** In seven
   libpostal English dictionaries, a small in-memory inspection found 958 nonblank
   rows, 2,085 distinct lowercased surface forms and 75 surface forms associated with
   multiple canonical strings. Examples: `st` → street/saint; `dr` → drive/doctor;
   `fl` → fall/flat/floor; `l` → lane/level; `bl` → boulevard/bowl/block. Some collisions
   are spelling equivalents, not semantic conflicts; 75 is not an error count.
   Method: split each nonblank line on `|`, use its first field as canonical, union
   canonical strings by each surface form. Files: `street_types`, `street_names`,
   `personal_titles`, `directionals`, `unit_types_numbered`, `level_types_numbered`,
   `post_office`, all `.txt`, at the pinned [libpostal English dictionary directory](https://github.com/openvenues/libpostal/tree/25099c506612b34b23b1bfe286ca6321fcf06f35/resources/dictionaries/en).
2. **Country and component role both matter.** NZ Post uses `RD` for Rural Delivery;
   expanding it indiscriminately to Road corrupts a legitimate address form.
   Canada Post specifies `CRT` for Court, while the Australian table specifies `CT`.
   Shared English vocabulary does not imply one universal postal convention.
   [NZ Post](https://www.nzpost.co.nz/business/shipping-in-nz/addressing-standards),
   [Canada Post](https://www.canadapost-postescanada.ca/cpc/en/support/articles/addressing-guidelines/symbols-and-abbreviations.page),
   [Australia Post](https://auspost.com.au/content/dam/auspost_corp/media/documents/Appendix-01.pdf).
3. **Typed source fields make augmentation safer.** AddressNet varies a separately
   identified street type, street suffix and state. It does not need to guess which
   part of an already flattened string is the suffix. Our structured G-NAF adapter
   has similar source information before merging into our coarser output fields.
   Preserve that distinction when generating variants; do not restore fine-grained
   public labels merely to augment data. [AddressNet generator](https://github.com/jasonrig/address-net/blob/28e7c2de030bae56f81c66d7e640dcc2d04fdfb6/addressnet/dataset.py).
4. **More repositories do not necessarily mean more independent data.** Deepparse's
   dataset derives from libpostal; Senzing also uses OSM/OpenAddresses and modifies
   the training data. Our repository already uses these source families. Treat
   re-renderings as variants, not new geographic diversity or independent validation.
   [Deepparse data](https://github.com/GRAAL-Research/deepparse-address-data/blob/ecb77e4ec86d82b4ed61d973adc67f5b6a7dd150/README.md),
   [Senzing](https://github.com/Senzing/libpostal-data/blob/5113929832ac06619d18a4816f78a90fef8cc7a3/README.md).

## Highest-value GitHub resources

### 1. libpostal: dictionaries and the training generator, not its browser runtime

Inspected dictionary documentation, seven English dictionaries, the ambiguity list,
and the abbreviation-generation implementation.

- [Dictionary format and categories](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/resources/dictionaries/README.md): canonical forms and alternatives are grouped by semantic category. Ambiguous expansions are explicitly recognized.
- [Training abbreviation implementation](https://github.com/openvenues/libpostal/blob/25099c506612b34b23b1bfe286ca6321fcf06f35/scripts/geodata/address_expansions/abbreviations.py): probabilistic selection, language filtering, capitalization preservation and punctuation variants. Its default probabilities are implementation choices, not established optimal rates for us.
- [English dictionaries](https://github.com/openvenues/libpostal/tree/25099c506612b34b23b1bfe286ca6321fcf06f35/resources/dictionaries/en): street types, directionals, units, floors, post-office terminology, names and ambiguity exclusions.
- [Saint/street issue](https://github.com/openvenues/libpostal/issues/73): illustrates why choosing one expansion requires context.

Use a reviewed subset for training variants and collision tests. Do not flatten all
categories, sample obscure variants uniformly, or install libpostal in the browser.
Code is declared MIT; the training data has separate source-dependent terms.

### 2. usaddress + Parserator: lexical cues and targeted failure repair

Inspected [feature extraction and tokenization](https://github.com/datamade/usaddress/blob/aa7699b53a0843fc443f9e87285b88cbd9eaf50a/usaddress/__init__.py),
[training guidance](https://github.com/datamade/usaddress/blob/aa7699b53a0843fc443f9e87285b88cbd9eaf50a/training/README.md),
the training-file inventory and [Parserator training](https://github.com/datamade/parserator/blob/e9bed77ac75524084b2d8864985857a6c87b3746/parserator/training.py).

The model receives abbreviation, digit, punctuation, directional and street-type
features plus neighboring-token context. The text need not be globally expanded.
The contribution workflow centers on real failing patterns and different examples
of those patterns for regression testing.

Resources to examine for label-compatible US examples:
[`training/labeled.xml`, `multi_word_state_addresses.xml`, `us50_messiest_manual_label.xml`](https://github.com/datamade/usaddress/tree/aa7699b53a0843fc443f9e87285b88cbd9eaf50a/training).
Keep their explicitly synthetic OSM/OpenAddresses files in the same source families
as our existing data. These are candidate development/training resources, not
automatically clean holdouts. Map labels and punctuation boundaries before reuse.

Code is MIT. The US50 files have a separate
[NCSA-style attribution notice](https://github.com/datamade/usaddress/blob/aa7699b53a0843fc443f9e87285b88cbd9eaf50a/raw/LICENSE.md).
Do not assume a root license is the entire data provenance story. Do not infer from
upstream's small-example training advice that a few examples will fix our model.

### 3. AddressNet: the most directly relevant structured-data augmentation example

Inspected [data generation](https://github.com/jasonrig/address-net/blob/28e7c2de030bae56f81c66d7e640dcc2d04fdfb6/addressnet/dataset.py),
[CSV conversion](https://github.com/jasonrig/address-net/blob/28e7c2de030bae56f81c66d7e640dcc2d04fdfb6/generate_tf_records.py)
and [prediction/normalization](https://github.com/jasonrig/address-net/blob/28e7c2de030bae56f81c66d7e640dcc2d04fdfb6/addressnet/predict.py).

It constructs labeled Australian strings from G-NAF fields, varies state/suffix
forms, unit/floor presentation and separators, and introduces character noise.
It rebuilds labels alongside generated strings. Prediction separately canonicalizes
certain closed-vocabulary fields using similarity matching.

Borrow the typed generation pattern. Do not copy its randomization rates, arbitrary
component shuffling, fuzzy correction or ASCII-only vocabulary. In particular, noise
on postcode/house-number identifiers can change the address rather than simply its
presentation. Our returned text must remain what the user supplied.

Repository archived, last inspected commit from 2020; MIT code, G-NAF terms separate.
This is an algorithm reference, not a modern TensorFlow dependency recommendation.

### 4. Pelias parser: keep original spans and alternative interpretations

Inspected [Span](https://github.com/pelias/parser/blob/f8808981ea23c99126ea2e1e98b1ed8f7891fe01/tokenization/Span.js),
[normalizer](https://github.com/pelias/parser/blob/f8808981ea23c99126ea2e1e98b1ed8f7891fe01/tokenization/normalizer.js),
[postcode classifier](https://github.com/pelias/parser/blob/f8808981ea23c99126ea2e1e98b1ed8f7891fe01/classifier/PostcodeClassifier.js)
and the test inventory.

Spans retain original body/start/end while having a normalized view and candidate
classifications. Useful architectural precedent if we ever introduce normalized
features. Our existing tokenizer/decoder already supplies the crucial raw-offset
contract; do not import its graph/solver machinery to get that benefit.

Its [country tests](https://github.com/pelias/parser/tree/f8808981ea23c99126ea2e1e98b1ed8f7891fe01/test)
are a source of cases to inspect, not a ready-made accuracy benchmark: multiple AU
unit-address assertions are commented out. Its postcode classifier contains a limited
country list and positional assumptions, so copying it would not automatically cover
our seven countries. Code MIT; bundled external resources require separate review.

### 5. OpenCage address-formatting: presentation templates and fixtures

Inspected [English abbreviation configuration](https://github.com/OpenCageData/address-formatting/blob/cbf23487c13ad437cadab0083ef79fe5f1d1823e/conf/abbreviations/en.yaml),
the [abbreviation fixture](https://github.com/OpenCageData/address-formatting/blob/cbf23487c13ad437cadab0083ef79fe5f1d1823e/testcases/abbreviations/en.yaml),
NZ fixtures and the seven-country fixture inventory.

Resources: [`conf/countries/worldwide.yaml`, `conf/state_codes.yaml`, `testcases/countries/`](https://github.com/OpenCageData/address-formatting/tree/cbf23487c13ad437cadab0083ef79fe5f1d1823e).
Useful for plausible country-specific ordering and omission behavior. Its stated
scope is display formatting, not a complete postal-mail grammar; apartment/floor
and PO-box coverage must come from other resources. Our libpostal-derived data may
already inherit these templates, so this is not automatically new variation.
Declared MIT. No reason to add a template engine for a few controlled variants.

### 6. usaddress-scourgify: normalize by parsed component, not globally

Inspected [constants](https://github.com/GreenBuildingRegistry/usaddress-scourgify/blob/cf66bdc42aebc57d48fe41e32e108fdcde347e3c/scourgify/address_constants.py)
and the normalization call flow. Separate dictionaries give `ST` a city-name meaning
of Saint and a street-type meaning of Street. This is a concrete example of why
field-aware normalization is safer than whole-string replacement.

It targets US formatting and says it does not validate addresses. Its uppercase,
abbreviated outputs, postal-code repair and optional geocoder path are not our
extraction contract. Reuse terminology/test ideas, not the full dependency or an
automatic correction layer. Declared MIT.

### 7. Google libaddressinput: small postal metadata, not free-text parsing

Inspected [metadata specification](https://github.com/google/libaddressinput/wiki/AddressValidationMetadata),
[normalizer source](https://github.com/google/libaddressinput/blob/81eb9628382b07d371d8ea0b11badf7de3857fd5/cpp/src/address_normalizer.cc)
and [licensing statement](https://github.com/google/libaddressinput/blob/81eb9628382b07d371d8ea0b11badf7de3857fd5/README.md).

Country records describe formatting, expected fields, administrative keys and
postcode patterns. These can inform diagnostics and a small country-scoped feature
experiment. A pattern match does not prove postcode existence, deliverability or
country identity. Do not reject partial addresses just because postal-validation
metadata says a mailing address requires more fields.

Code Apache-2.0; metadata CC-BY-4.0 according to the README. If used later, pin a
snapshot for the seven countries rather than fetch metadata during browser parsing.
There is no country hint in our current API: benchmark-only gold country metadata
must not silently become an inference input.

## Additional prior art: useful limits and alternatives

| Resource and inspection depth | What it contributes | Decision / declared terms |
| --- | --- | --- |
| [Nominatim](https://github.com/osm-search/Nominatim/blob/d6211ccd538d50cce5e87b48d2090a5f4183b60e/settings/icu-rules/variants-en.yaml): English rules and official tokenizer docs | Multiple searchable variants, suffix-position rules and explicit exceptions such as avoiding Drive-In abbreviation | Learn ambiguity handling; geocoding/index normalization is not span extraction. Repository GPL-3.0; file cites OSM and USPS sources. Do not copy wholesale. |
| [Deepparse](https://github.com/GRAAL-Research/deepparse/tree/62ffae3489111911db7b64066ca31dfb05a7d308): cleaner, metric and docs | Subword representations; current cleaner handles whitespace, case, commas and a specific unit/number hyphen pattern | Comparator, not a new runtime. Its `metrics/accuracy.py` measures per-tag accuracy, not whole-address exact spans. LGPL-3.0 code. |
| [Deepparse data](https://github.com/GRAAL-Research/deepparse-address-data/tree/ecb77e4ec86d82b4ed61d973adc67f5b6a7dd150): README/inventory | Clean/incomplete examples; special hyphenated unit-address data with automatically revised labels | Related libpostal lineage, not independent gold. Repository declares MIT; retain and inspect upstream provenance before reuse. |
| [Senzing/libpostal-data](https://github.com/Senzing/libpostal-data/tree/5113929832ac06619d18a4816f78a90fef8cc7a3): release/data documentation | Corrected source renderings and public difficult-address evaluation material | Already used here. Preserve protections; do not mix its benchmark into training. Root Apache-2.0 is not blanket source-data clearance. |
| [DueDil UK parser](https://github.com/duedil-ltd/address-parser/tree/d0ee26c8fb3609b0200b209e75fd57b103e4e93c): README/inventory | Character tagging, PAF-derived presentations, omission/reordering | Archived MIT project. Abbreviation injection is listed as a TODO, not a demonstrated result. PAF is not supplied and requires access; no new open UK corpus here. |
| [BharatAddress](https://github.com/Neelagiri65/bharataddress/tree/dbd512f4baf5602789c7c51555ed234eacc4fefa): preprocessing, dictionaries, parser, aliases and evaluator | Layered cleanup, unit/building vocabulary, postcode lookup | Pattern inspiration only; India-specific enrichment and inferred fields do not fit this release. Evaluator uses substring tolerance. MIT code, embedded-data terms separate. |
| [Pelias Placeholder](https://github.com/pelias/placeholder): README screening | Geographic containment resolves ambiguous administrative names | Useful explanation of errors requiring external geographic knowledge. SQLite gazetteer service is outside our small offline parser. MIT code; geographic data separate. |
| [PostGIS/PAGC](https://postgis.net/docs/Extras.html): official documentation screening | Lexical categories, place-name tables and ranked parsing rules; right-to-left administrative analysis | Historical hybrid prior art, not a PostgreSQL dependency to add. Code/data terms must be checked at the component before copying. |
| [Philadelphia Passyunk](https://github.com/CityOfPhiladelphia/passyunk): README/metadata screening | City-specific parsing backed by street/centerline information | Shows what restricted geography plus lookup can buy. Not a seven-country parser; some data private and no root license identified by GitHub metadata. Reference only pending terms review. |
| [OpenAddresses](https://github.com/openaddresses/openaddresses): source-registry screening | Structured records to render with exact labels, source attribution registry | Already part of our source lineage. No automatic new acquisition: identify coverage gaps first. Registry/code license does not replace each dataset's terms. |

Nominatim's [tokenizer documentation](https://nominatim.org/release-docs/develop/customize/Tokenizers/)
explicitly separates normalization, transliteration and generation of searchable
variants. This distinction is worth retaining even though we should not ship its
pipeline. Likewise, canonicalizing an already extracted component helps matching or
display; it does not by itself improve the field boundaries already predicted.

## Postal resources to consult before writing rules

These define intended postal conventions, not the complete range of acceptable user
input. Use them to source variants and counterexamples, not impose a validity gate.

| Scope | Resource | Useful checks |
| --- | --- | --- |
| US | [USPS suffixes](https://pe.usps.com/text/pub28/28apc_002.htm), [unit designators](https://pe.usps.com/text/pub28/28apc_003.htm) | Street/unit vocabulary; ambiguous tokens across field roles |
| CA | [Canada Post abbreviations](https://www.canadapost-postescanada.ca/cpc/en/support/articles/addressing-guidelines/symbols-and-abbreviations.page), [civic addresses](https://www.canadapost-postescanada.ca/cpc/en/support/articles/addressing-guidelines/civic-address.page) | Unit-before-number hyphens, province abbreviations, street types; retain proper names |
| AU | [Australia Post addressing appendix](https://auspost.com.au/content/dam/auspost_corp/media/documents/Appendix-01.pdf), [official tools/resources](https://auspost.com.au/business/shipping/letters/domestic-sending/large-volume-letters/mail-barcoding/barcoding-tools-guides) | Unit-number slash variants; do not treat floors and suites as interchangeable slash forms |
| NZ | [NZ Post addressing standards](https://www.nzpost.co.nz/business/shipping-in-nz/addressing-standards) | Rural Delivery, mailtown, units, PO boxes and Private Bags |
| IE | [An Post sending guide](https://www.anpost.com/Post-Parcels/Sending/Sending-Guide), [address guidance](https://www.anpost.com/Post-Parcels/Sending/Correct-Address) | Locality/town, Dublin postal districts, Eircode and building-name addresses |
| ZA | [SA Post Office parcel addressing](https://www.postoffice.co.za/questions/howtoaddressparcel.html) | Postal-code placement and mailing format; not a comprehensive abbreviation lexicon |
| UK | [OpenCage GB fixtures](https://github.com/OpenCageData/address-formatting/blob/cbf23487c13ad437cadab0083ef79fe5f1d1823e/testcases/countries/gb.yaml), [Royal Mail PAF context](https://www.royalmail.com/personal/receiving-mail/update-your-address) | Useful fixture and address-source references, not a verified complete open UK abbreviation table |

No equivalent complete, openly reusable abbreviation lexicon was established in
this pass for every country. Do not fill those gaps with invented country rules.

## Research papers: what they support, and what they do not

- [Leveraging Subword Embeddings for Multinational Address Parsing](https://arxiv.org/abs/2006.16152)
  motivates subword-aware models for address variation. It does not establish a
  benefit from pre-expansion or prove its architecture fits our download budget.
- [Deepparse system paper](https://arxiv.org/abs/2311.11846) describes fine-tunable
  multinational parsing. Its broad accuracy claims need metric and corpus alignment
  before comparison; the current implementation's per-tag metric is a concrete warning.
- [Fighting crime with Transformers: address parsing in payment data](https://arxiv.org/html/2404.05632v1)
  constructs noisy training presentations informed by 1,600 manually labeled payment
  messages: names, country forms, rearrangement, omissions, line separators and
  unrelated material. The useful lesson is **measure the target input distribution
  before designing noise**, not adopt every corruption. Payment data and its labels
  differ from our product. Its corpus descends from Deepparse/libpostal, so it is not
  independent geographic supervision. The paper claims released assets; this pass
  did not establish a separate downloadable asset suitable for immediate ingestion.

No inspected paper or repository establishes how much abbreviation handling will
improve our H128. No accuracy projection is justified before our own controlled test.

## Smallest experiment worth doing

### A. Inspect the completed baseline, without changing it

Use development errors and successes to measure abbreviation sensitivity, separately
from wrong source labels, missing country coverage, punctuation and unit/number
boundary errors. Pair natural examples with controlled full/short forms. Include
negative controls: Saint names, NZ `RD`, `FL`, initials, proper names, numeric ranges
versus units, postcode-like house numbers and inputs without abbreviations.

Score our seven-field task, not an upstream fine-grained task: units, floors, house
numbers and roads already map to `street_address` here. Better separation of those
internal pieces is not itself a product improvement. The useful outcome is better
street-address/locality/city boundaries and correct labels elsewhere.

Our current tokenizer already ignores inter-token whitespace when gap features are
off. Adding whitespace tidying alone is not a new model capability. Existing
`prepare.variant` handles case/layout/omission, but rebuilding only labeled components
can drop unlabelled material; do not blindly reuse it for noisy natural input.
The running seven-country corpus uses admitted originals plus online casing changes;
the existence of older variant code does not mean all those variants are active.

### B. One matched abbreviation augmentation comparison

Starting from the same completed checkpoint, run an unchanged control and an augmented
treatment for the same budget with identical optimization settings, country exposure
and shuffle schedule. Where exact optimizer state is unavailable, initialize both
arms identically and call them continuations, not exact resumes.

Start with common, country-appropriate, component-typed forms. Prefer transforming
known full forms into short forms to resolving ambiguous short forms. Use source
subfields where available; otherwise skip uncertain substitutions. Retain original
presentations, regenerate offsets, preserve outside-address text and validate bounds.
Do not copy upstream augmentation rates as if validated for us. Pick and record one
conservative pilot rate after inspecting natural development prevalence.

Split source entities before generating variants; variants stay with their original
split and retain lineage. Count augmentation as additional presentations, not additional
addresses. Check collisions with protected evaluation inputs. Public upstream tests
used to design the treatment are development tests, not untouched final evaluation.

### C. Conditional follow-up, not a simultaneous architecture project

If augmentation helps but leaves a repeated lexical problem, compare:

1. A tiny frozen-model, context-limited normalized-feature experiment, preserving
   source spans and excluding ambiguous/multi-token rewrites initially.
2. Only if that is inadequate, a small retrained lexical-feature experiment inspired
   by usaddress (for example street-type/unit/postcode-shape indicators).

The latter changes the feature/export/browser contract and is therefore more work
than training-only augmentation. Do not quietly add it to the active training run.
Treat postcode patterns as evidence, not hard overrides. Do not use gold country
labels as hidden runtime hints. Do not correct city names or infer missing fields.

### D. Keep or delete based on actual value

Select on equal-country exact ordered-span development accuracy; report each country,
abbreviation and non-abbreviation slices, and fixed-versus-broken examples. A paired
uncertainty check on address groups is useful for marginal differences. A handful of
synthetic wins or a macro improvement hiding a large country regression is insufficient.
Freeze the candidate before confirmatory testing; do not tune on the pipeline's test
outputs. Measure browser cost only if runtime code changes.

If gains are negligible, publish the qualified baseline and stop this branch. No
unconditional retraining campaign, giant rule table, geocoder service, new labels,
pretrained Transformer download or dependency framework follows from this survey.

## Reuse and licensing boundary

License names above are observed upstream declarations, not redistribution clearance.
Record the exact file, revision, source attribution and applicable terms before any
copy or data ingestion. Code, dictionary, dataset and trained-weight rights may differ.
Our own licensing remains undecided as requested. This document introduces links and
analysis only; it does not vendor third-party resources or change the publication gate.
