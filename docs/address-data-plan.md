# Coverage-first Latin-script training data

**Closed — 16 September 2026.** No further acquisition or annotation is planned.
The [closeout and publication plan](closeout.md) supersedes this workstream;
the material below is retained as historical evidence.

Research and repository audit: September 15, 2026. Versioned corpus built and
independently verified. No new
model is promoted by this document. This is the acquisition workstream of the
[consolidated next plan](address-next-research-plan.md). It supersedes English-language
filtering and the earlier arbitrary corpus/admission caps.

## Execution status

Current materialized version: `data/latin-20260915/diagnostic-v4/manifest.json`.
It contains 4,343,094 unique training records (391,479,199 compressed bytes), with
192 countries/territories represented and all 249 enumerated in `coverage.json`.
Independent full-row verification passed; this is provisional source supervision,
not an accuracy result or worldwide-readiness claim.

The final consolidation accounts for 4,442,246 approved input occurrences:
77,320 duplicate occurrences collapsed; 21,820 unique protected-overlap pairs and
12 conflicting text/label pairs quarantined. Original aliases and source-specific
exclusions remain in the hash-bound input builds. Train/dev/test, coverage, index,
consolidated streams and reports have SHA-256 bindings; natural dev/test remain
eight unscored examples each.

| Country | Retained unique training records |
| --- | ---: |
| India | 13,276 |
| Vietnam | 6,533 |
| Ireland | 60,279 |
| Australia | 1,445,784 |
| New Zealand | 1,579,052 |
| South Africa | 973,205 |
| Kenya | 511 |
| Nigeria | 689 |
| US | 19,195 |
| UK | 14,987 |

These counts attribute identical text/label examples to the retained occurrence;
they are not physical-entity counts. AU/NZ/ZA account for 92.06% of retained rows.
Fifty-seven inventory entries have no retained rows; 43 represented entries have
neither a number-and-road nor a building/unit/floor example. Nigeria and other thin
sources remain acquisition priorities. Do not interpret large retention as balanced
exposure or fill those deficits with repeated variants. Broader natural evaluation,
targeted source acquisition, and measured exposure comparisons remain necessary.

Independent verification checked every training row's spans, labeled token round
trip, Latin eligibility, flags/provenance, and recomputed SQLite identity fields.
All country/source/type totals reconciled; the 538-source multiset exactly matches
the five input builds. Known normalized-text, group, dual-street, source-entity and
model-input protection checks found zero retained overlaps. Retained exact/model-label
conflicts and unemitted indexed identities were also zero. All 1,641 input, eight
protected and nine output hashes passed, as did the 16 pinned natural examples.
The full-row/index comparison used counts and two 256-bit hash aggregates (XOR and
modular sum): a probabilistic reconciliation, not a literal per-row SQL join.
An exact retained-key comparison against v3 found 602 additions and zero removals.
All 4,442,246 source aliases were also checked for protected-key leakage. Verification
took 570 seconds wall time with 221,069,312 bytes peak RSS alongside other work.
This verifies structural correctness, not the semantic truth of every source label.

Manifest SHA-256:
`b68bf76a52db56b5270062859f86555a4c63b9340c28af7f3ecf6a2c64aac38e`.
Training SHA-256:
`6dd935694398addccc6c843b507c48b05ba44bbb71dddbc38748b1112c1be105`.

### Next data work: use the remaining scanned tail-country pools

A second census used the repository's `address_type()` on unique exact text/label
pairs, verifying candidate/report hashes against `consolidated-v2/report.json`.
These are full-source **candidates before semantic admission and current protection
gates**, not exact unused counts or physical entities:

| Country | Number + road | Road without number | Building/unit/floor |
| --- | ---: | ---: | ---: |
| Bangladesh | 11,142 | 5,744 | 6,172 |
| Ghana | 1,013 | 378 | 927 |
| Indonesia | 14,645 | 15,133 | 60 |
| Kenya | 100 | 528 | 47 |
| Sri Lanka | 917 | 2,991 | 148 |
| Nigeria | 245 | 442 | 25 |
| Nepal | 642 | 1,505 | 399 |
| Philippines | 9,038 | 24,055 | 3,793 |
| Pakistan | 653 | 1,657 | 327 |

The next admission wave should review these existing non-administrative pools:
PH/ID/BD provide the largest available increases, while NG/GH/KE address particularly
thin African coverage. Nigeria's entire non-administrative pool is only 712 unique
pairs, so complementary acquisition remains necessary even if every label were
usable. Review mapping families and their unresolved variants; do not approve these
counts from structure alone, subtract final coverage counts to infer exact unused
sets, or resurrect an arbitrary per-country retention cap. Apply full-source
conflict/protected-alias gates before staging the next immutable supplement.

Nigeria review is complete: `ng-review-v1/queue-all.json` freezes all 712
non-administrative unique pairs and their 1,188 source occurrences, split into two
356-pair review assignments only for parallel work. Sol-medium reviewers inspected
every assigned row with a second pass. Final semantic QA inspected all 52 proposed
changes plus a deterministic 40-row sample; two unsupported suburb conversions were
restored to their original candidates and marked uncertain. The final review has
602 accepted and 110 uncertain pairs; these are AI judgments, not human gold.
[Final semantic QA](evidence/ng-final-semantic-qa-20260915.json)

`ng-supplement-v1` stages 602 unique pairs across 1,015 occurrences. All 26,117 source
occurrences reconcile: 24,929 administrative/unreviewed and 173 uncertain occurrences
remain quarantined. Full-source conflict/protected-alias gates removed no additional
accepted occurrences. Independent output QA passed: all 14 input, eight protected,
and five output hashes; all source IDs exactly once; every staged/quarantined review
decision; and all 602 recomputed SQLite identities. Independent global-conflict and
protected-key recomputation found zero staged hits. The five-build global merge into
`diagnostic-v4` completed with 4,343,094 rows. Nigeria now has 689 unique examples:
252 number-and-road, 359 road-only, 46 building/unit/floor, 28 administrative and
four other partials. These are final reviewed label categories, not the original
queue categories. Full independent v4 verification passed; the verified v3
remains unchanged. v4 manifest SHA-256:
`b68bf76a52db56b5270062859f86555a4c63b9340c28af7f3ecf6a2c64aac38e`.
Supplement manifest SHA-256:
`fbaa98bb98aea9f43c1dd2b185ce649782f45ac2628520575b7c513d6ce858bd`.

The Nigeria generator subsequently received formatting-only changes for CI. Its
exact build-time source (hash `16805c9bdde51a607fef069574eadb993db7011d57487e744c08988fb2bcd7ac`)
is preserved at `data/latin-20260915/source-snapshots/16805c9bdde51a607fef069574eadb993db7011d57487e744c08988fb2bcd7ac.py`.
The supplement manifest still records the original working path/hash; use this
snapshot to verify that historical generator input. Corpus files/manifests were
not rewritten to disguise a code-version change.

Next, broaden the 16-example natural evaluation beyond its current
business/institution convenience sample and continue complementary tail-country
acquisition. Corrected ordered H128, CPU/MPS padding/batch checks, full-corpus
disk-backed loading and untrained float32/int8 WebGPU fixture parity are now complete.
Controlled fresh training/exposure comparisons and trained-model qualification remain
open. Do not launch a default proportional run merely because this version is complete.
[Implementation qualification](evidence/ordered-h128-v2-qualification-20260915.json)

Training preparation now counts eligible rows rather than retaining every row index
for a bounded sample, preserving the same seeded selection. Unlimited training spools
eligible raw JSONL to a temporary file, retaining only 64-bit offsets; each epoch
globally shuffles those offsets and encodes one batch at a time. No retention cap or
country-ordered shuffle buffer is introduced. File provenance hashes stream through
the existing helper. All 17 Python tests pass, including sampling, gap-feature parity,
global-permutation parity, and temporary-file cleanup on success and failure.

A loader-only check on the first 10,000 real v3 rows took 0.234 seconds to spool and
0.233 seconds to read all rows in shuffled 64-row batches; zero rejected, 80,000 offset
bytes, 16,425,454 temporary bytes, process peak RSS 206,258,176 bytes. This small check
is not full-training throughput. A subsequent full-v3 loader check admitted all
4,342,492 rows with zero rejections: 87.724 seconds to spool, 594.796 seconds to read
every globally shuffled row in 64-row batches (about 7,301 rows/second), 34,739,936
offset bytes, 6,277,508,842 temporary bytes and peak process RSS 206,028,800 bytes.
The temporary file closed and was removed after completion. This ran concurrently
with corpus merging/QA, not as an isolated benchmark; no model training was involved.
Other consumers of `load()` retain their existing list behavior.

### Acquisition and audit record

`gpu-address corpus inventory|audit|coverage` now implements the first stage, using
the existing PyArrow dependency and stdlib SQLite for disk-backed collision counts.
The current inventory is `data/latin-20260915/inventory.json`: 249 ISO countries and
territories, 240 represented in this source, 247 shards, 19,824,796,303 compressed bytes.
Unscanned row counts are unknown, not zero. All selected shards are scanned in full.

Raw audit outputs are staging candidates, not automatically approved training
labels. The completed provisional base and reviewed supplements are recorded below;
the combined train/dev/test version is not complete until its merged manifest exists.
No country/category/street caps apply. Exact-text conflicts and lossy-key
collisions are reported without deleting records; street groups are not entity IDs.
The legacy `prepare`/`expand` workflows are not the new-corpus admission path.

The HF mapper now preserves original whitespace and Unicode offsets rather than
reconstructing text. Acquisition streams bytes and validates pinned source checksums.
Historical data and models remain unchanged; no new dependencies were introduced.

Completed full scans: Bangladesh, Ghana, Indonesia, Ireland, India, Kenya, Sri Lanka,
Nigeria, Nepal, New Zealand, Philippines, Pakistan, Vietnam, and South Africa.
Together: 7,488,401 raw rows, 7,320,483 Latin candidates. The sum of per-country
unique text counts is 5,077,840, not a count of physical entities or a globally
deduplicated corpus. [Results and reproduction commands](evidence/corpus-audit-20260915.json)

The qualitative mapping pilot flagged Indian building/floor content incorrectly
tagged as number/road; see `data/latin-20260915/mapping-review.json`. Kenya and Nigeria
remain thin in street/premise examples despite scanning their full files. Ireland,
New Zealand, and South Africa contain substantial unused coverage. No labels receive
blanket semantic approval from these counts. Input limits rejected no Latin rows in
this formatted-source batch; that does not measure natural missing-space boundaries.

## Objective

Parse addresses from any country when written in Latin/Roman script. Preserve local
names, accents, romanizations, punctuation, spelling, and exact input spans. Do not
require English vocabulary, infer absent fields, translate input, or pass country
metadata to the model. Native non-Latin script support is not required.

An ideal corpus is not merely large or perfectly formatted. It must cover countries,
address types, and real input variation; use consistent labels; retain provenance;
and have protected evaluation. Absolute semantic perfection cannot be certified,
especially with AI-only review. Record measured quality and remaining deficits.

## Why the previous expansion failed to close coverage gaps

Verified against `expand.py`, the existing acquisition manifest, and source files:

- The expansion explicitly selected 15 countries, omitting Vietnam and New Zealand.
- It sampled 12,000 rows per country file before selecting useful address types.
- Of India's sampled 12,000 candidates, 11,140 contain only administrative/place
  fields; only 335 contain both a house number and road. Egypt has the same problem:
  10,326 administrative-only rows and 750 number-and-road rows.
- Source/category caps limit excesses but establish no country coverage floor.
- Inherited data and generated variants remain part of the reported row count.
- G-NAF's locality is deliberately omitted rather than having its mapping resolved.

Full source scans reveal unused candidates:

| Country file | All rows | Number + road rows | Distinct normalized texts with road | Distinct road names |
| --- | ---: | ---: | ---: | ---: |
| India, already cached | 714,698 | 18,528 | 34,416 | 10,926 |
| Vietnam, previously unselected | 80,491 | 9,533 | 10,823 | 1,671 |

These are pre-admission counts, before Latin-script filtering, semantic checks,
entity grouping, and evaluation exclusions. Distinct text is not distinct physical
address. Both files are from Deepparse revision
`cb61e5e49db87f8c3586b5494149f612460f8992`; Vietnam's Parquet is only 532,433 bytes.
The existing 12,000-row sample was representative of its file's row distribution,
not of the task's required address-type distribution.

## 1. Build a country coverage inventory before acquisition

Include every country/territory in the intended worldwide scope, even where the
available count is zero. Record raw rows, Latin-script rows, accepted source records,
estimated entity groups, distinct roads/localities, source families, address types,
and exclusions with reasons. Do not count case changes or transliterations as new
geographic coverage.

Rank acquisition by deficits in accepted entities and address types, not solely by
the small public benchmark. First tranche: India, Vietnam, New Zealand, Ireland,
and Australia; preserve South Africa, US, and UK coverage. Then work through other
thin-country buckets, including African, South/Southeast Asian, Caribbean, and
romanized-address coverage, according to the inventory rather than another fixed
short country list.

Coverage checkpoints, not corpus caps, sufficient-data claims, or training gates:

- The earlier 10,000 priority-country / 2,000 other-country proposals may flag thin
  coverage, but do not stop acquisition at them or discard additional useful records.
  Prioritize measured missing localities, address types, and independent entities.
- Seek multiple localities and at least two genuinely different source families for
  priority countries. Country size and addressing conventions require exceptions.
- Missing coverage remains an explicit deficit. Never manufacture thousands of variants
  to mark a country complete, lower label standards, or silently exclude a country.

Count source records, estimated physical-address entities, and street/locality groups
separately. The existing `group_id` often represents an entire street, not one address.
Multiple houses or units on one street are not automatically duplicates.

## 2. Reuse existing sources correctly; acquire only missing coverage

### First: country-partitioned tagged data

Enumerate all country files and all shards at a pinned revision. Stream and validate
approved files, retaining eligible originals without arbitrary per-country row caps.
Record acquisition bytes/time/storage budgets; where a budget requires partial
acquisition, record exactly which shards/row groups were covered and what is missing.
Do not silently fall back to the first shard or compressed archive prefixes.

Separate corpus retention from training exposure. A bounded sample is appropriate
for a mapping pilot or controlled experiment; it is not the final retained corpus.
The existing Parquet sampler scans the batches anyway, so its 12,000-row limit is
not a scan-I/O saving. Millions or tens of millions of useful records are acceptable
if acquisition, validation, storage, and measured training budgets support them.

Deepparse provides 240 subsets and derives its data from libpostal. Treat it and
Senzing/libpostal variants as related source families, not independent corroboration.
Its punctuation-free tagged text is training material, not untouched natural gold.
[Dataset card](https://huggingface.co/datasets/deepparse/worldwide-addresses)

### Second: structured address sources for remaining holes

- Use G-NAF for Australia, resolving locality semantics before admitting complete
  rendered records. Preserve real units, floors, building names, and source IDs.
  [Official source and terms](https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf)
- Overture Addresses provides hundreds of millions of records, but its current
  coverage is 39 countries and does not include India or Vietnam. It can supplement
  NZ and many European/American countries, not solve all tail-country gaps. It
  aggregates OpenAddresses and other sources; retain upstream lineage and source
  licenses. Its address IDs are not stable across attribute changes, so do not use
  those alone for cross-release leakage protection.
  [Coverage and construction](https://docs.overturemaps.org/guides/addresses/)
- For uncovered countries, inspect OSM country extracts for explicit address tags
  and attested Latin names. Use source IDs and available geographic metadata for
  grouping and review, never as model hints. OSM incompleteness must stay visible.
  [Vietnam](https://download.geofabrik.de/asia/vietnam.html),
  [India](https://download.geofabrik.de/asia/india.html)

No assumption that a postcode directory, road network, or gazetteer is a set of
complete addresses. These can support administrative/name examples and consistency
checks, not invented building-number/street/locality combinations.

### Complementary: natural inputs for fields and formats structured sources miss

Reserve natural evaluation sources early and acquire missing natural patterns alongside
structured data. The source ladder ranks reuse cost, not an instruction to postpone
natural data until the structured corpus is complete.

Audit bounded source-diverse raw strings from public business/institution pages,
existing WDC data, AllThePlaces, and Overture Places. Verify that text is genuinely
raw before classifying it as natural; assembled structured fields stay rendered.
Business chains are a biased slice, not residential or rural coverage.
[AllThePlaces](https://github.com/alltheplaces/alltheplaces),
[Overture Places quality limitations](https://docs.overturemaps.org/guides/places/)

India's newer raw/labeled corpus is worth a bounded audit for building, landmark,
and rural patterns. Its source card and examples show mixed reviewer provenance,
overlapping labels, and privacy caveats. Remap/review; never treat the word "gold"
as validation. Do not blindly copy source `houseNumber` into our house-number label.
[Labeled data](https://huggingface.co/datasets/gagan1985/indian-addresses-gold),
[raw source and redaction notes](https://huggingface.co/datasets/gagan1985/indian-addresses-raw)

Retain source-specific reuse terms and attribution. Unclear rights or unresolved
personal-data issues block that source, not the entire build; seek another source.

## 3. Establish a consistent label contract before bulk admission

Reuse the existing field schema and span validation. Write short source/country
mapping examples for city/suburb/district/county, building versus unit, rural village,
landmark versus road, floor, PO box, and repeated components. Geographic administrative
levels are not interchangeable across countries. Metadata may corroborate labels,
but cannot supply values absent from the input.

Resolve uncertain mappings by review or quarantine the record. Do not delete a
locality from a full address to hide mapping uncertainty, and do not leave an
unannotated address component as `O` in a supposedly fully labeled training row.
Genuine partial addresses remain valid; absence of postcode/country is not an error.

Keep raw strings unchanged. Normalization used for matching/deduplication is separate
from model text. Label typos as they occur; this is extraction, not postal validation.
Implausible postcode/city pairs trigger review, not automatic rejection of natural
noisy input. Conflicting structured records must not seed synthetic geography.

For AI curation, label before seeing student predictions, then do a second pass on
boundaries and semantics. Record `ai-reviewed`, reasons, and uncertainty. Use a random
sample to estimate audit agreement and a separate difficult sample to discover bugs;
do not combine the two into an accuracy estimate or claim independent human gold.

## 4. Protect evaluation and group entities before rendering variants

Reserve new natural development/test sources first. Keep public benchmarks, prior
reviewed sets, and their known entities protected. Existing source splits remain
protected unless their reuse is explicitly documented and no longer evaluated as
held-out data.

Group exact input duplicates and known source entities. Lossy normalized keys flag
candidate matches, not proven duplicates: the existing punctuation-stripping key
collides for `12-14 Main Street` and `1214 Main Street`. Use coordinates plus address
attributes to review cross-source near duplicates when available. Accent-folded and
romanized matches need the same caution. Audit apparent over-grouping too.

Assign all renderings, partial forms, case/accent variants, and transliterations of
one entity to the same split. Hold out domains/brands for natural examples. Keep a
separate street/locality-held-out generalization slice; it is stricter than unseen
entities and must not become a global deletion rule for unique training addresses.
Keep current protected exclusions until reconciled, rather than loosening them to
grow the corpus. Independently sourced evaluation is still needed: different wrappers
around OSM are not independent datasets.

Deduplication improves evaluation integrity in broader NLP research, but no published
gain is assumed to transfer numerically to this parser.
[Lee et al., ACL 2022](https://aclanthology.org/2022.acl-long.577/)

## 5. Assemble a country-balanced, address-type-diverse corpus

Maintain separate buckets for street/premise addresses with locality context,
building/unit/floor-rich addresses, rural/village/landmark addresses, PO boxes,
genuine partial addresses, administrative-only fragments, and non-address distractors.
"Has house number + road" is a diagnostic, not a universal definition of completeness.

Retain the clean originals independently of the training mixture. Record source,
country, type, and entity information in the existing manifest/output metadata; a
simple reproducible exposure policy suffices, not a sampling framework.

- Measure country/type/source concentration and unique-entity exposure. Preserve
  diverse records from large countries; address domination through training exposure.
- Compare source-proportional and country/type-balanced exposure at one informative
  corpus size. Uniform countries is a testable design, not known production traffic.
- Do not fill a country's missing street/rural/building coverage with admin fragments.
  Their proper exposure depends on the task mix and measured validation results.
- The previous 5% country, 10% admin, 1,000 rich-record, and 30% augmentation values
  are unvalidated hypotheses, not acceptance gates. No fixed million-row target.
- Begin the scale comparison with originals. Test controlled augmentation separately
  so its benefit is not confounded with additional real geographic coverage.

Use deterministic shuffled exposure across shards, not the same tiny permanent subset
each epoch. Record unique records seen and repeat exposure so balancing cannot hide
starvation of large sources or repeated memorization of tiny-country pools.

## 6. Add bounded, source-backed variation only after coverage

Render verified components using country-appropriate templates and preserve labels
while changing separators, line breaks, case, common abbreviations, or omitting fields.
Use attested Latin aliases first; any generated transliteration is explicitly synthetic
and reviewed for the relevant naming convention. Never require diacritic stripping at
inference. Recompute offsets after every training transformation.
[OpenCage templates](https://github.com/OpenCageData/address-formatting)

Use observed natural errors to choose typo/spacing patterns. Do not arbitrarily shuffle
every country into US order, transplant random cities/postcodes, or generate millions
of LLM-written addresses. Do not put synthetic variants into the natural test set.
Address research supports target-shaped noise rather than assuming clean structured
data represents messy inputs.
[Hammami et al., NAACL 2024](https://aclanthology.org/2024.naacl-industry.17/)

Keep tokenizer-unrepresentable natural examples in the audit/evaluation denominator.
Training may quarantine them temporarily, but a measured representation deficit must
be resolved or explicitly reported before claiming readiness. Quantify it by country
and type, including the 512-code-point / 128-token / 64-byte-token limits. Do not
claim excluded examples became supported simply because the remaining score rose.

## 7. Data acceptance and claim boundaries

1. Every requested country/territory has an inventory entry, acquired/accepted counts,
   address-type coverage, and an explicit remaining-deficit status.
2. Priority-country deficits and acquisition constraints are explicit. Coverage
   checkpoints are not sufficient-data guarantees; variants do not fill entity deficits.
3. Every admitted row has source/version/license lineage, label provenance, and a split
   group. All spans, ordering, token-label round trips, and encoding checks pass.
4. No known cross-split exact/entity overlap or unresolved conflicting labels remain;
   near-duplicate checks and their limitations are recorded.
5. Each source/country mapping passes an initial small pilot and a blind random semantic
   audit before scaling. Audit accepted and rejected tail-country records first, with
   sample counts and uncertainty. Systematic errors block the affected mapping batch
   until repaired; sampling cannot certify perfection.
6. AI-reviewed natural dev/test sets are source/entity-disjoint, include full and partial
   inputs, and disclose ambiguity, unsupported-script, and tokenization coverage.
7. Corpus distributions and training exposure are separately declared, with exceptions
   visible. Total rows alone can never establish worldwide readiness.

These requirements protect admitted data and honest reporting, not an impossible
promise of perfect data in every country before any experiment. Diagnostic training
may use a validated, explicitly incomplete version; worldwide release claims may not
hide those deficits. Freeze evaluation design and freshness before comparing models.

## Minimal implementation and execution order

Reuse `prepare.py`/`expand.py`, PyArrow streaming, the existing span/tokenizer checks,
and JSONL. Replace whole-corpus accumulation in audit/build/loading with bounded
processing where memory measurements require it; stream checksums too. A streaming
trainer alone does not fix preprocessing memory. Rebuild in a new data directory;
re-audit inherited rows instead of treating the old corpus as automatically trusted.
Do not modify historical corpora/checkpoints.
No new annotation platform, database service, registry, or training framework.

Execution order:

1. Inventory every country; fully scan the already available India and newly identified
   Vietnam files, grouped by address type. Resolve mapping pilots before scaling.
2. Establish protected natural evaluation and coherent locality/building policies.
3. Fill country deficits from tagged data first, structured national/OSM sources second,
   and targeted natural curation where those sources lack the required input patterns.
4. Deduplicate/group/split and retain clean originals; specify balanced training
   exposure separately. Add variants only for a declared augmentation comparison.
5. Produce train/dev/test JSONL, quarantine reasons, source/checksum manifest, and one
   coverage/quality report. Treat those as the deliverable before starting training.

The known H128 padding defect must be corrected before subsequent training, but it is
not a reason to postpone this data work. This campaign does not add architectures,
teachers, or browser features.

### Premise policy and conflict extraction — September 15

The annotation policy now explicitly accepts premise-led addresses without a road,
including Indian apartment/wing/floor/building lines. Coarse source fields are mapping
issues, not evidence that such addresses are invalid. No global keyword relabeling or
new output field was added. The user's example is a development regression fixture,
not natural held-out evaluation evidence; its exact spans survive encoding/decoding.

Ran `uv run gpu-address corpus conflicts --data data/latin-20260915 --countries in vn`.
The new per-shard `conflicts.jsonl.gz` files preserve every candidate occurrence:
India has 9 conflicting exact texts across 186 rows; Vietnam has 10 across 527 rows.
These are review queues, not adjudicated labels or a deduplicated corpus. Original
candidate streams and the historical mapping-review artifact remain unchanged.
Cross-shard conflicts and evaluation exclusions are now handled by the staging
consolidation below; final source/entity admission is separate.

Next: adjudicate these queues under the updated policy, reserve fresh natural
evaluation sources, and only then admit repaired/deduplicated rows. Review random
non-conflicting rows too: agreement between source labels does not imply correctness.

The first conflict adjudication pass is recorded in
`docs/evidence/source-conflict-review-20260915.json`: all 19 texts reviewed,
3 accepted decisions covering 9 source occurrences, 16 unresolved texts covering
704 occurrences. Accepted decisions reference exact original source rows and SHA-256
identities; no source labels or candidate streams were overwritten. A second check
by the same AI reviewed the decisions; this is not independent or human agreement.
Validated complete queue coverage, source hashes, selected-row existence and raw span
offsets against both conflict streams. No student predictions were inspected.

These reviewed inputs and their newly consulted evidence pages are development
material, ineligible for a fresh final evaluation. The artifact records this explicitly;
enforcement in the final corpus builder remains pending. Accepted decisions
are not training admission: deduplication, split protection and broader source mapping
review still apply. Next unresolved policy issues are Vietnamese ward hierarchy and
kilometre locators; bare city/street homonyms must remain uncertain without context.

### Global consolidation and fresh review — September 15

`gpu-address consolidate` completed all 14 audited shards without a retention cap.
The completion manifest is `data/latin-20260915/consolidated-v2/report.json`:

- 7,320,483 input candidate occurrences; 5,076,985 unique exact text/label pairs.
- 2,243,498 duplicate occurrences collapsed, with original source streams retained.
- 21,646 pairs quarantined for protected overlap; 348 for exact label conflicts.
- 5,054,991 retained **staging** candidates, not semantically approved training rows.

SQLite bounds index memory; original candidate streams preserve duplicate lineage.
Exact text is not normalized away. Both historical road+city and road+postcode
protection apply, including alternative groups carried by duplicate occurrences.
The earlier incomplete `consolidated/` directory has no completion report and must
not be consumed. No historical corpus or checkpoint was overwritten.

Reproduction (run from repository root with a new output directory):

```sh
uv run gpu-address consolidate --data data/latin-20260915 \
  --output data/latin-20260915/consolidated-v2 \
  --protected data/multisource/public-benchmark.jsonl.gz \
  data/multisource/dev.jsonl.gz data/multisource/source-dev.jsonl.gz \
  data/webgpu/dev.jsonl.gz docs/evidence/natural-ai-review.jsonl \
  docs/evidence/natural-complete-ai-review.jsonl \
  docs/evidence/natural-pilot-20260915.jsonl
```

Conflict addendum decisions resolve 8 of the 19 India/Vietnam texts (40 original
occurrences); 11 texts/673 occurrences remain uncertain. Consolidation deliberately
does not apply these decisions automatically. The ward and kilometre policies are
now documented. Random non-conflicting mapping review covered 100 rows across India,
Vietnam, New Zealand, Ireland and South Africa: 68 accepted, 32 uncertain. This is
not a source-wide accuracy estimate or permission to admit an entire country batch.

The fresh natural pilot now has 8 dev and 8 test rows across eight countries,
materialized by `docs/evidence/prepare-natural-pilot.py` into `natural-v1/`.
All 16 pass encoding/span round trips. Source domains are reserved and no predictions
were inspected. The two adjudication addenda must be applied: protecting only the
initial tentative labels misses subsequently resolved street keys. This tiny
institutional/business convenience sample is not representative or human gold;
historical training/entity overlap review is recorded below.

Four complete small AllThePlaces snapshots contribute 827 source features from
India, Vietnam, Kenya and Nigeria, with unchanged extracted strings, hashes and
individual AI review. They are business-chain-biased complementary inputs, not
residential/rural coverage or byte-identical original HTML. Uncertain labels and
missing strings remain in the review ledger. A plausible Circle K/RMIT Vietnam
co-location at 702 Nguyễn Văn Linh is explicitly protected even though existing
normalized text and street keys miss it; generic keys cannot prove entity disjointness.

G-NAF now retains the primary postal locality and separates address-detail entity
IDs from street-locality grouping. Its cached 2022 shard is still only one of ten;
full cached-shard audit and semantic admission are separate from this mapper repair.
The initial full scan found 27,720 rows rejected by the legacy required
number/road/postcode rule. Sample review included valid lot-led and partial addresses.
The mapper now renders attested lots when civic numbering is absent and permits
missing road/postcode; a second full audit measures the recovered coverage. When both
lot and civic number exist, the civic rendering explicitly records the unused lot
alternative rather than pretending it was absent. Principal-only source selection
remains an explicit slice, not a claim that historical or alias addresses are invalid.

The remaining combined deliverable is validated train/dev/test, retained quarantine,
a checksum/source manifest and country/type/source coverage for all 249 inventory
entries. The 5.05 million raw staging candidates are not blanket-approved labels.

### First admitted pilot

`data/latin-20260915/curated-v2/manifest.json` records 592 retained ATP training rows:
India 60, Vietnam 351, Kenya 113, Nigeria 68. All 827 reviewed source features are
accounted for: 222 quarantined (210 unresolved, 9 missing text, 3 protective
exclusions) and 13 exact duplicate aliases. Original review decisions are unchanged.
The materializer is `docs/evidence/prepare-atp-training-pilot.py`; run its
`--selfcheck` before reproducing into a new output directory. The manifest references
the final natural dev/test paths and hashes; `coverage.json` enumerates all 249
inventory entries with admitted counts, source-audit status and explicit deficits.

This completes a **small admitted diagnostic pilot**, not the coverage campaign.
Its address-type counts are 89 building/unit/floor, 387 number+road, 95 road-only,
19 administrative and 2 other partial inputs. Labels remain AI-reviewed; source
chains and input types are concentrated. No new training has started. The larger
provisional builds below supersede this pilot's size, not its coverage limitations;
broader acquisition and declared training exposure remain open.

The [freshness audit](evidence/natural-freshness-20260915.json) checked 39 local
files (1,165,360 rows) and 26 saved run configurations, without model predictions.
The two current historical training streams total 697,689 rows and contain no
exact, normalized, group or dual-street matches to the 16 pilot inputs. Lexical
Jan Smuts matches refer to Cape Town/Elsiesriver rather than the Johannesburg
target. All 16 may remain in a protected new-from-scratch diagnostic; this is not
proof of complete physical-entity disjointness. The older WebGPU file hashes do
not match the current stream, and the missing old snapshots prevent certifying
freshness against those historical checkpoints. Multisource hashes do match.

### Provisional larger-source admission

The [G-NAF second audit](evidence/gnaf-full-audit-20260915-v2.json) recovered
27,720 lot-led/partial records. A subsequent full source-field check found another
mapper omission: letter-only unit/floor designators disappeared when the numeric
subfield was empty. The [third audit](evidence/gnaf-full-audit-20260915-v3.json)
checks their preservation and quarantines 13 range ends missing their numeric
endpoint rather than inventing one. It retains 1,453,928 candidate occurrences,
including 507 letter-only flats and 400 letter-only floors. Six composite dugout
premises remain semantically uncertain and are excluded from admission.

The corrected standard audit is
`structured-v2/audit/au-gnaf-2022-shard0.parquet/`: 1,453,926 unique text/label
pairs, two duplicate occurrences, no exact/model-input label conflicts. It completed
in 278.51 seconds with 278,495,232 bytes peak process RSS on this Mac. The earlier
65 apparent duplicate occurrences partly reflected the lost secondary designators.
Source fields and address-detail IDs remain available; known G-NAF entity IDs
protect historical held-out renderings. Earlier audit versions are preserved but
superseded for admission. The interrupted `diagnostic-v1/` has no final manifest;
the corrected build uses a new `diagnostic-v2/` directory.

The [prospective NZ/ZA review](evidence/nz-za-partition-review-20260915.json)
examined 192 blind source occurrences, excluding prior-reviewed texts. NZ simple
number+road and road-partial partitions, and ZA simple number+road, each had 32/32
accepted samples. These support provisional source-supervised diagnostic use after
conflict/leakage gates, not semantic certification. ZA road-partial had 6 unresolved
samples and is not approved. The remainder contains valid addresses too and stays
retained; these are mapping partitions, not global validity or completeness rules.

`docs/evidence/assemble-data-version-20260915.py` reuses the existing disk-backed
consolidator for these sources and the curated pilot. It preserves known conflicts
from the complete 14-source staging pool, even when a competing annotation is outside
an approved partition. No new variants or historical training mixture are silently
added. Country/type/source counts describe retention, not a decided exposure policy.
`diagnostic-v2/manifest.json` is now complete: 4,035,361 source occurrences yielded
4,009,104 unique exact text/label pairs, with 21,820 protected pairs withheld and
3,987,284 retained provisional training rows. The 26,257 duplicate occurrences
remain traceable to preserved inputs. These counts describe the seven-country base,
not the final merged version or independent physical entities.

The inherited-original re-audit and IN/VN/IE reviews below are complete. They restore
reviewed breadth without unioning the already-expanded historical training set.
Known source-dev, natural and public evaluation protections remain in force.

### Reviewed first-tranche supplements

The India number/road queue is now fully reviewed: 4,621 unique texts representing
all 5,523 original occurrences. The three AI curation parts accepted 3,032 texts;
independent checks put nine of those back into adjudication. Nineteen explicit
parenthesized road aliases received a recorded span-consistency overlay. Original
review files and source annotations remain unchanged; uncertainty is not `O`.

`in-ie-vn-supplement-v1/manifest.json` completes a staging supplement with 87,258
occurrences: India 3,662, Ireland 75,865, Vietnam 7,731. All 1,181,419 source
candidates are accounted for; unselected records remain in quarantine. Ireland's
three uncertain texts have six source occurrences. Vietnam's revised number/road
predicate still admitted prior known problems, so the full expanded risk family
(36 texts, 51 occurrences) is withheld, not just the initial five examples.
Remaining IE/VN supervision is provisional source mapping, not individual AI labels.

The inherited-original audit verified 448,777 original occurrences and recovered
source hashes for the legacy base subset. Of these, 377,296 pass the Latin/mechanical
gate; this alone grants no admission. A fresh non-query US/UK audit inspected 448
occurrences and carries forward earlier findings. Recurring unit/floor and explicit
borough/city errors block five broad source partitions. A further GeoPlanet review
covered 160 fresh and 30 prior non-US administrative fragments; two unresolved
hierarchy cases and their field-equivalent variants remain withheld. Administrative
fragments do not fill missing street/premise coverage.

`inherited-supplement-v1/manifest.json` is complete with 51,337 staged occurrences
from reviewed US/UK and GeoPlanet partitions. It checks exact/model-input conflicts
and protected aliases across **all** originals before selecting approved partitions;
filtering first would hide conflicts carried by an unapproved source. Historical
source slices remain explicitly partial; retaining them does not claim full raw
acquisition. Neither supplement's occurrence count can simply be added to the base's
unique-row count to obtain the final training size.

Fresh regional reviews now cover the remaining non-US/UK, non-GeoPlanet inherited
source families across Europe, Asia, Africa, the Americas and Oceania. They carry
forward prior findings and apply targeted field-family gates, not whole-country
rejection because one sampled row is uncertain. Resolved Japanese numbering and
Philippine regional conventions remain usable; source placeholders, composite
premises/roads and unresolved administrative mappings remain quarantined with their
aliases. `world-supplement-v1/manifest.json` completes 267,275 staged occurrences
across 183 countries and 475 source entries; 181,502 quarantined occurrences account
for the rest of all 448,777 originals. All 1,427 output hashes and every candidate's
source binding, spans, and token round trip passed verification. The final merged
unique count is reported above after cross-supplement consolidation.

This remains provisional, sampled source supervision, not individual certification
of every retained row. All 249 country entries must retain explicit deficits; thin
or administrative-only coverage does not establish premise, rural or natural-input
coverage. The protected natural set remains only 16 AI-reviewed business/institution
examples, not human gold or representative evaluation. Known source/entity/street
protections do not prove complete physical-entity disjointness. Training exposure is
still undecided and no training has started. Final merged train/dev/test, source
checksums and country/type/source coverage now exist and passed independent full-row
verification. The versioned-corpus deliverable is complete; the broader coverage
campaign and model-training plan are not.

The final merge is `docs/evidence/finalize-data-version-20260915.py`. It verifies
completed input manifests and protected-file hashes before creating a new output,
then reuses the shared consolidator. Protection propagates across identical model
inputs, including differently formatted aliases whose entity ID is known only in
another source. A regression test covers that case. The final manifest also binds
the consolidated index, candidate stream, report, and combined inventory.

```sh
uv run python docs/evidence/finalize-data-version-20260915.py --selfcheck
uv run python docs/evidence/finalize-data-version-20260915.py \
  --output data/latin-20260915/diagnostic-v3
```

The output is consumable only after its completion manifest exists. Reproduction
requires the preserved input builds; use a fresh output directory, not an overwrite.
