# Next plan: evidence before limits

**Closed — 16 September 2026.** The [closeout and publication plan](closeout.md)
supersedes all next steps below. No additional training, curation or architecture
experiments are planned. This document remains historical evidence.

## Current execution — September 16

The seven-field migration and bounded India-data comparison supersede the historical
September 15 "next" steps below. Both matched runs and all evaluations are complete.
The new batch gets 35/168 fresh India addresses correct versus 34/168 for the control,
with US/UK/ZA/NZ regressions. Do not promote or scale that recipe. Next: correct the
existing India complete-address exposure and diversify annotations beyond Assam;
do not start another architecture experiment or call the next run final retraining.
See the [fixed protocol, findings and results](evidence/seven-india-experiment-20260916.md).

Critical review: September 15, 2026. This is the authoritative execution plan.
It replaces the earlier experiment ladder, including its premature "closed" verdicts,
English-only recommendations, and assumed corpus ceilings. Detailed acquisition work
lives in [the data plan](address-data-plan.md); annotation rules live in
[the annotation policy](address-annotation-policy.md). No training or runtime changes
are implemented by this planning update.

## Implementation progress — September 15

### Current decision: casing robustness experiment next

Balanced-v5 training and both epoch evaluations are complete. Final epoch public
agreement is 39.63% (epoch 1: 42.31%); natural exact spans are 173/220 (epoch 1:
176/220). Do not interpret the historical pending statements below as current status.

The bounded diagnosis found 95.8% agreement on sampled training presentations but
severe casing sensitivity: the final checkpoint's US public agreement rises from
175/2,233 to 1,803/2,233 when only input case changes to uppercase. This is a diagnostic,
not a deployable accuracy improvement. India additionally has a natural-supervision
gap: only 31/359 newly AI-reviewed, untrained examples match exact spans.

**Current experiment:** launched `runs/ordered-h128-case-v6-scratch-20260915` using
the same H128, balanced-v5 corpus, seed 2026, batch 128, learning rate 0.002 and two
epochs on MPS. Only training-time case variation changes: uniform per-presentation
original/lower/upper/title token-byte features, with a separate seeded RNG so shuffle
order stays matched. Original labels/text/offsets remain intact; Unicode expansions
that exceed the token-byte limit fall back to the original example and are counted.
This mix is an experimental choice, not an optimum. All 28 Python tests pass.

Both epoch checkpoints are retained. The submitted job automatically evaluates both
on the existing public/natural sets, then runs the training/source-dev and casing
diagnostics on the final checkpoint. Results remain pending. No 359-row merge,
country-weight, tokenizer, architecture or teacher change is included. The 359 remain
an untrained diagnostic for this experiment.

Reproduction: `uv run python docs/evidence/run-case-v6-20260915.py` (new run/output
directories required; no automatic overwrite or restart).

[Evidence, 100-error review and exact next experiment](evidence/balanced-v5-diagnosis-20260915.md).

### Country expansion and matched-budget experiment

Latest execution: both baseline epochs completed (3,942 seconds of training).
Epoch 2 public field agreement is 4,606/12,868 (35.79%), versus 39.18% at epoch 1;
natural ordered-span agreement is 178/220 (80.91%), with complete examples still
3/8. Preserve both checkpoints rather than trusting the eight-row dev selector.
The epoch-1 WebGPU export passed all 29 fixtures in both float32 and int8 on the
Mac's non-fallback Metal adapter; this establishes runtime parity, not accuracy.

The ready expansion contains 139,155 US/UK examples, 710 provisionally mapped
Indian companion examples, 18 individually AI-reviewed companion examples, and
27 independently second-reviewed raw Indian examples. The raw review held 21 of
48 examples for uncertainty. This is a first tranche, not a retention ceiling.
The balanced-v5 build applies final duplicate/protection gates before exposure.

Balanced-v5 is materialized: 139,404 new unique model inputs survived final gates
(19 protected, 479 existing-input duplicates and eight internal duplicates were
excluded). Its 4,343,094 exposures cover 2,060,208 unique pool rows. US/UK/India
receive 105,656/95,832/79,224 exposures; AU/NZ/ZA together receive 39.16% rather
than 92.06%. Retained source data is unchanged. Fresh training was launched as
`runs/ordered-h128-balanced-v5-scratch-20260915`, MPS, batch 128, two epochs,
seed 2026 and learning rate 0.002. Accuracy and export qualification remain pending;
do not promote the run merely because its data distribution is less concentrated.

[Epoch-2 evaluation](evidence/ordered-h128-v4-epoch2-all-public-natural-evaluation-20260915.json),
[actual WebGPU parity](evidence/ordered-h128-v4-epoch1-webgpu-20260915.json).

The user authorized US/UK expansion, Indian label reconciliation, and another H128
run. All six US/UK Parquet shards are downloaded: 197,730,382 US and 87,758,821 UK
source rows. These are not unique premises or automatically approved supervision.
UK chunk 0 is entirely administrative-only; its 3,954,129 street-bearing rows are
in chunk 1. US rows include 132,293,964 numbered-road and 7,404,994 unit-bearing
examples. Source order makes prefix/first-shard sampling unsuitable.

`prepare-us-gb-expansion-20260915.py` retains the complete pinned raw reservoir and
selects an explicitly budgeted, deduplicated exposure across all shards. It does
not claim global reservoir deduplication. The first selection requests 139,155
street/unit examples; semantic gates, conflicts, and protected evaluation matches
can reduce the final yield. There is no permanent source-row or street cap.

The Indian alternative is downloaded and profiled. Its 4,370,606 raw rows contain
substantial premises/landmark variation; the 4,834-row labeled companion needs
schema reconciliation. A source `houseNumber` containing a flat, shop, room, or
floor is **not an annotation-error count**. Preserve valid addresses and reconcile
the broader source premises field with our explicit unit/level convention. Exact
text and tokenizer-incompatible boundaries remain visible, not silently rewritten.

`build-balanced-exposure-20260915.py` materializes a 4,343,094-row training exposure
using square-root weights of the frozen v4 country/address-type counts. Keeping
reference weights fixed prevents a newly acquired large source from purchasing
most training exposure. This is a testable hypothesis, not an optimal distribution
or a population estimate. Source retention is unchanged; repeated exposure is
intentional. Match baseline seed, model, batch size, epochs and optimizer settings;
report actual elapsed time because matching examples/updates is not identical GPU
compute when input lengths differ. The existing training loader is unchanged.

The first v4 checkpoint is snapshotted and evaluated on protected sets: 5,042 of
12,868 public examples match every field (39.18%). US/UK/India strict field-map
agreement is 3.90%/31.37%/7.41%; inspected failures include both schema conventions
and genuine unit/floor/PO-box mistakes. AI-reviewed natural ordered-span agreement
is 173/220, but only eight carry the historical complete flag (3/8 exact). Neither
the mostly partial natural set nor the eight-row training dev set justifies a
release claim. Evaluate both completed epochs and the revised model with the same
saved-source evaluator before interpreting improvement.

[US inspection](evidence/us-shards-inspection-20260915.json),
[UK inspection](evidence/gb-shards-inspection-20260915.md),
[India inspection](evidence/india-alternative-profile-20260915.json),
[epoch-1 evaluation](evidence/ordered-h128-v4-epoch1-all-public-natural-evaluation-20260915.json).

Execution update: the user prioritized training over further evaluation work.
Launched `runs/ordered-h128-v4-scratch-20260915` from fresh weights on the complete
4,343,094-row v4 corpus: MPS, batch 128, two epochs, seed 2026, learning rate 0.002,
default PyTorch thread count, no initialization checkpoint and no sample cap.
This is the full-corpus baseline, not a release/final-accuracy claim. It deliberately
uses the current source-proportional mixture and existing eight-row dev set; their
imbalance/selection limitations remain. Expanded natural annotations stay separate
and unadmitted. Do not delay this baseline for further curation or claim that its
recipe is optimal before observing results.

The bounded real optimizer-step probe measured 154 rows/s on CPU at batch 64,
1,170 rows/s on MPS at batch 64 and 1,738 rows/s on MPS at batch 128. It used a
4,096-row uniform sample, four warmup updates and fresh weights per case; it is a
throughput comparison, not an accuracy comparison. Full shuffled disk I/O and long
thermal behavior were not measured by this probe.
[Measured throughput](evidence/retraining-throughput-20260915.json).

The first data milestone is implemented and executed: `gpu-postal corpus` inventories
every pinned source shard and performs uncapped, disk-backed audits. Full scans of
14 countries examined 7,488,401 rows and retained 7,320,483 Latin-script staging
candidates. Peak process RSS was 207,159,296 bytes (about 198 MiB); those initial audit
artifacts occupied about 2.58 GiB. No model was promoted.
[Measured evidence and commands](evidence/corpus-audit-20260915.json)

The inventory covers 249 ISO countries/territories: 240 have files in this source,
with 247 total shards. This source/reference inventory is not a geographical support
whitelist. Missing source files and unaudited countries remain explicit deficits.

The mapper now preserves source text/offsets; downloads stream and verify hashes.
The new audit does not merge punctuation-folded matches or cap street groups. It
retains duplicates/conflicts for subsequent adjudication and records their counts.
The old lossy helpers remain for historical workflows and protected exclusions.

Targeted AI review found building/floor text mislabeled as house_number/road in the
India source. Findings are recorded at `data/latin-20260915/mapping-review.json`;
this is not a population error estimate. Formatting checks cannot approve these labels.
The mapping policy and protected natural pilot are now materialized. The base build
retains 3,987,284 unique provisional training rows; reviewed IN/IE/VN, US/UK/GeoPlanet,
and wider inherited sources add separately staged supplements. The four-build merge
is complete at `data/latin-20260915/diagnostic-v3/`: 4,342,492 unique training rows,
192 represented countries/territories, all 249 inventory entries reported. Independent
full-row, hash, protection and count verification passed.
The subsequent Nigeria review and five-build v4 merge are also independently
verified: 4,343,094 rows, Nigeria 87 to 689, exactly 602 additions and no removals.
[Current data-build status and remaining deficits](address-data-plan.md)

Known label defects, unresolved field classes, conflicts, and protected aliases are
quarantined; original records remain available. Source mapping audits do not certify
every retained label. The natural pilot has only eight dev and eight test examples,
so representative natural evaluation and country/type coverage remain open.
Corrected ordered-H128 source, strict version checks and CPU/MPS invariance tests
are implemented. Float32 then int8 browser fixtures pass on the Apple Metal adapter
with gap features off and on. These use untrained weights; fresh training, broader
evaluation and trained-model browser/quantization qualification remain pending.
[Implementation qualification](evidence/ordered-h128-v2-qualification-20260915.json)

## Keep the goal; distinguish it from implementation choices

- Worldwide addresses written in Latin/Roman script, including local names,
  diacritics, and romanizations. Not English vocabulary or English-speaking countries
  only. Native non-Latin script support is not required.
- Text-only input; exact original substrings and offsets; no country hints,
  translation, geocoding, or inferred missing fields.
- Highly accurate, small-download, fast browser inference using WebGPU.
- H128 is the chosen candidate; H192 remains parked. That is a scope decision, not
  proof that H128 is optimal or that larger models cannot help.
- Minimal Python setup and browser runtime. Minimal machinery does not mean a small
  corpus, weak checks, or an inadequate training budget.
- Preserve historical corpora, checkpoints, and measurements. Build new versions.

The previous 90% accuracy, 500 kB Brotli, 250 kB preference, under-3 ms warm median,
and 0.1 percentage-point quantization-loss numbers are documented working targets,
not research-derived limits. Retain them for continuity, explicitly define the metric
and workload before promotion, and report tradeoffs. They do not justify discarding
data or claiming success on an unrepresentative test. No new numeric country floor
is silently made a user requirement.

## Critical decisions audit

"Verified" below means established by local code or recorded experiment evidence.
"Untested" means the policy or causal conclusion lacks adequate evidence, not that
its opposite is automatically correct.

### 1. Acquisition caps became corpus limits — verified, remove in the rebuild

`expand.py` selects 15 countries, only their first Parquet shard, samples 12,000 rows
before categorizing them, and admits at most 5,000 number-and-road / 1,000 other rows
per source/country plus eight per street-like group. None is an established optimum.
The Parquet sampler already scans batches through the file.

Separate retained corpus, training exposure, and per-experiment compute. Enumerate
all countries/shards and retain eligible originals within recorded storage/acquisition
budgets. Do not permanently discard useful records merely to balance training.

### 2. Our replacement quotas were also guesses — untested, demote to checkpoints

10,000/2,000 entities, two sources, 1,000 rich examples, a 5% country cap, 10% admin
fragments, and 30% augmentation were proposed heuristics, not demonstrated optima.
Nor is one million rows an optimal final size. Record actual diversity and deficits;
use balanced exposure experiments to choose a mixture. A second website mirroring
the same source does not satisfy source independence.

### 3. "Entity groups" and street groups were conflated — verified

`prepare.group()` groups an entire road within a city or postcode. It is useful for
a strict geographic holdout but is not a physical-address ID. An eight-record group
cap can discard different premises and unit/building patterns on the same street.

Track source records, estimated physical entities, exact texts, and street/locality
groups separately. Keep entity relatives in one split; report street-held-out
generalization separately from ordinary unseen-entity generalization.

### 4. Aggressive normalization was treated as identity — verified collision

`prepare.identity()` removes punctuation and whitespace after NFKC/casefold:
`12-14 Main Street` and `1214 Main Street` have the same key. The key feeds dedup,
conflict detection, and split protection in several callers. This proves a collision
risk, not a measured corpus-wide false-merge rate.

Use exact/source-backed evidence for deduplication; treat lossy normalized,
accent-folded, and romanized matches as candidates for comparison. Audit false
merges and missed duplicates before changing shared identity logic. Preserve existing
evaluation exclusions while reconciling them; do not loosen protection just to add rows.

### 5. Structural validation was mistaken for semantic quality — unresolved

Valid spans and token-label round trips do not prove that a country-specific
"District" means city_district. The global HF mapping and G-NAF locality omission
need source/country pilots. Review filters such as municipality certification,
alias exclusion, placeholder-road rejection, and postcode requirements for what
they actually exclude. They can be appropriate for synthetic source admission,
but are not universal rules for recognizing natural addresses.

Keep complete source-backed labels or quarantine unresolved records. Do not turn
uncertain address fields into O or omit them to claim complete supervision.
Audit both accepted and rejected samples to measure selection bias.

### 6. Clean geography and full street addresses were overprivileged — untested

Number + road is one address type, not a worldwide definition of completeness.
Rural routes, villages, named premises, PO boxes, missing postcodes, partials,
and mistyped natural inputs belong in scope. Parsing is not postal validation.

Do not delete natural incorrect geography merely because it is implausible, or fill
absent fields from metadata. Do not fabricate inconsistent geography when rendering
structured records. Use address-type coverage, not a single completeness flag.

### 7. Script support was confused with language metadata — scope correction

English-only metadata filtering loses valid Latin-script names. ASCII filtering
also loses required diacritics. Define script eligibility using Unicode script
properties, including combining marks and Common characters; retain numeric-only
partials for review instead of requiring an English word. Mixed-script inputs get
an explicit out-of-scope/diagnostic classification, not a non-address label.

Preserve original normalization forms and offsets. Test composed/decomposed accents
and Python code-point versus browser UTF-16 offsets. Unicode defines script
properties, not an address-language classifier. [Unicode UAX #24](https://unicode.org/reports/tr24/)

### 8. Tokenizer limits were assumed harmless — verified restrictions, impact unmeasured

The encoder rejects inputs over 512 code points, 128 tokens, or 64 UTF-8 bytes per
token. It cannot place a field boundary inside `Delhi110001`. By default,
`12 Main Street` and `12\nMain Street` have identical model inputs; the existing
`gap_features` option preserves that difference.

Before bulk admission, count limit/boundary failures by country and address type,
and conflicting labels for identical model inputs. Keep those examples in the
coverage report. Test the existing gap option only if observed cases justify it;
make the smallest tokenizer change if a measured boundary ceiling warrants it.
Do not rewrite natural evaluation inputs to sidestep representation failures.

### 9. The historical baseline is not batch invariant — verified defect

The ordered-byte checkpoint's padding embedding is nonzero. Adding one byte-padding
column changes logits by up to 0.0943508 in the existing check; zeroing that embedding
reduces the difference to zero. An inference-only patch also changes predictions,
so historical weights must not be silently "fixed" and treated as the same baseline.

Restore the saved ordered H128 source into the normal training path with correct
padding, then establish a newly trained control. Check byte padding, token padding,
batch composition, and CPU/MPS inference. Existing tests of the unordered model do
not establish correctness of the ordered candidate.

### 10. "Exact accuracy" meant different things — verified mismatch

`evaluate.py` uses ordered label/start/end/raw component equality; `train.py` selects
best.pt on that metric on generated dev. Public diagnosis uses `teacher.field_map()`,
which normalizes NFKC/case/whitespace and concatenates repeated fields. Those metrics
are not interchangeable. The API returns spans, so field-content agreement alone
does not validate its contract.

For the next campaign, use ordered-span exact on policy-reviewed natural dev as
the primary selection metric, with country guardrails. Also report normalized
field-map exact for historical/baseline comparison, per-field span F1, counts, and
coverage. Keep generated dev as a diagnostic. Label every table with its metric.

### 11. Small, selected evaluation sets were treated as decisive — inadequate evidence

The 204 accepted AI-reviewed inputs contain 196 partials and only eight coarse
complete examples; 50 uncertain inputs were excluded. The 102-row test has already
been inspected. Neither its high agreement nor a gain of a few examples establishes
worldwide accuracy. Country results based on a handful of examples are unstable.

Create fresh source/entity-disjoint natural dev and test sets, sampling full and
partial, residential/business/rural, and country/type strata. Size them for the
decision precision and independent groups needed, not a convenient 250-row cap.
Report ambiguity/adjudication coverage and input-limit failures separately.
Conditional accuracy on accepted labels is not all-input accuracy. No confidence
interval repairs a biased convenience sample or systematic AI-label errors.

Use paired comparisons on the same rows and uncertainty estimates clustered by
source/entity where relevant. Repeat close/promising training comparisons with
additional seeds; a single seed is a screen, not evidence of exhaustion.
[Dror et al., ACL 2018](https://aclanthology.org/P18-1128/)

### 12. Balanced country scores were assumed to represent users — untested

Raw micro accuracy reflects the dataset mix; country macro weights a tiny country
slice equally with a large one. Neither estimates unknown production traffic.
Without actual traffic, declare an evaluation design, not a guessed user distribution.
Report both, per-country sample counts/uncertainty, and address-type/source slices.
An aggregate gain cannot hide a reproducible major tail-country regression.

### 13. "Converged" and "closed" exceeded the experiments — unsupported conclusions

The larger-data screen used one schedule/seed and generated-dev checkpoint selection.
H192 changed the frontend; GRU had less training than the final H128. Short crop and
prior-checkpoint-loss probes test those recipes, not all augmentation or distillation.
Two-epoch weights-only continuations reset AdamW; they are not uninterrupted training.

Retain negative results as bounded evidence. For a causal comparison, match the
relevant frontend, tokenizer, data, initialization, optimizer treatment, selection
metric, and compute; record differences explicitly. A fixed schedule is a control,
not proof it suits every data scale. Assess learning curves and limited schedule
adjustments before declaring a plateau. Budget affects model comparisons.
[Dodge et al., EMNLP 2019](https://aclanthology.org/D19-1224/)

### 14. A data-quality rebuild was being equated with "more rows" — incorrect framing

Country coverage, label repair, address-type mixture, raw versus rendered formats,
and row count are different interventions. A combined rebuilt-corpus run measures
the package benefit, not the causal contribution of each ingredient.

Use nested subsets of the same cleaned corpus to test scale; at one informative
size compare source-proportional and country/type-balanced exposure. Test augmentation
separately. Both small and large corpora can overfit; neither quantity nor
"natural" provenance guarantees correctness.

### 15. Local RAM was allowed to dictate the data frontier — implementation constraint

The unlimited loader keeps all encoded examples in a Python list. Acquisition audit
and build also accumulate large lists/maps; whole-file hashing reads add transient
memory. Merely changing the training iterator does not make the pipeline scalable.

Implemented since this audit: training provenance hashes stream through the existing
helper; bounded sampling counts eligible rows instead of retaining their indices,
with unchanged seeded selection. Unlimited training now uses temporary raw JSONL
with 64-bit offsets, globally shuffled per epoch and decoded one batch at a time.
Other `load()` consumers retain list behavior. The full-v3 loader-only check passed
all 4,342,492 rows: 87.724 seconds to spool and 594.796 seconds to read back globally
shuffled batches, with peak RSS 206,028,800 bytes. Full model-training throughput
remains unmeasured; the loader check ran alongside corpus merging/QA.

Measure peak RSS, swap, disk, and sustained examples/second. Stream acquisition,
validation, and training with bounded buffers, retaining sufficient shuffle across
shards/countries; use simple disk-backed grouping if measured memory requires it.
Reuse gzip/JSONL, PyArrow, stdlib, and PyTorch. No distributed framework or new service.
PyTorch supports iterable loading; actual M1 throughput remains a local measurement.
[PyTorch data loading](https://docs.pytorch.org/docs/stable/data.html)

### 16. Browser performance was transferred to an unported model — not established

The 168,001-byte / 1.8 ms measurement belongs to the older 205,452-parameter unordered
model, not the 159,308-parameter ordered candidate. Twenty-nine fixtures do not
qualify every input length, country, or quantization failure mode.

Do an early minimal ordered-frontend export/kernel feasibility check before a long
training campaign; finish full parity and quantized evaluation only for a finalist.
Measure end-to-end cold/warm p50/p95, CPU tokenization/CRF, readback, and actual
transferred bytes. M1 Chromium measurements are not universal browser results.
Do not add int6/QAT/new runtimes unless measured size or accuracy loss requires them.

### 17. Teachers, losses, and other encoders became predetermined "next unlocks" — unproven

Pretraining may help; a teacher is not the inevitable next step. Teacher agreement
can preferentially select easy/common-country rows and preserve shared source errors.
The current length-normalized CRF loss is also a modeling choice, not exact-match
optimization, but changing it without a measured symptom adds another confound.

Keep H128 and the existing loss for the corrected data baseline. After scale,
coverage, and optimization checks, route persistent errors: fix mappings/data for
source-specific failures, representation for input collisions, and consider one
teacher ceiling probe only for a remaining contextual/semantic bottleneck.
Any future pseudo-label admission audits disagreements and tail coverage as well
as agreement. No teacher or encoder sweep is authorized by this plan.

### 18. Every disagreement was implicitly assumed learnable — unproven

The same short input can genuinely denote different administrative levels or places
without country/context hints. More data cannot reveal information absent from the
input. Conversely, two labels for one input can be a mapping error rather than true
ambiguity. Distinguish policy inconsistency, missing representation, and genuinely
underdetermined text before deciding which intervention is justified.

Keep ambiguity/adjudication counts visible, use one consistent extraction policy,
and do not manufacture certainty or narrow the problem to easy inputs. The current
API returns `unassessed`, not calibrated confidence or address validity. Non-address
training examples should teach empty components; they do not create a validated
address-rejection classifier or authorize claiming one.

## Consolidated execution order

### Phase 1 — make the next result interpretable

- Freeze the Latin-script scope, annotation mappings, metric names, and evaluation
  membership. Old public/reviewed sets remain diagnostics and protected from training.
- Inventory every country/shard/type, including zero coverage. Audit both accepted
  and rejected rows, grouping collisions, source overlap, and tokenizer failures.
- Reserve fresh natural evaluation sources now; natural acquisition must not wait
  until all structured data has been exhausted.
- Prepare the corrected ordered-H128 training source and invariance tests.
- Run a bounded loader/throughput measurement and early browser feasibility check.

Deliverable: mapping/coverage pilot, evaluation specification, correctness checks,
and measured resource budget. The immediate work starts with the available India
and Vietnam files, not another model experiment.

### Natural evaluation expansion — execution specification, September 15

The frozen v4 corpus and its eight dev/eight test rows remain unchanged. New web
discoveries begin as an **unreviewed acquisition queue**, not an enlarged benchmark.
No predictions are needed to acquire, annotate or check overlap. Reuse JSONL, the
annotation policy, span validation and existing protection keys; no new service or
annotation framework.

Reuse audit: `data/webgpu/unlabeled-real.jsonl.gz` has 2,480 rows/713 hostnames
(SHA-256 `90cb8dea4804631df0a949078e3efbc365ae410dc3239002b5a8bdad31bba7f2`).
A full read found 2,317 Latin-script rows. Applying exclusions in order gives
163 non-Latin rows, 227 previously reviewed normalized texts, 471 additional
reviewed-host/subdomain matches, and 1,619 candidates across 447 hostnames. Of the
candidates, 1,139 have empty country hints. This checks the two prior natural-review
JSONL files and the 16-row pilot; it is not a training-overlap or related-brand
clearance. All 1,619 remain unreviewed, not new dev/test rows. The executable
`docs/evidence/queue-natural-expansion-20260915.py` writes the complete uncapped
candidate queue with source hashes; it was run to produce
`data/latin-20260915/natural-expansion-wdc-queue.json`.
The same run screens these candidates plus the ten targeted web discoveries in
`docs/evidence/natural-expansion-queue-20260915.json` against v4's retained SQLite
rows: **46 WDC candidates already match training text and model input**. None of
the ten targeted discoveries matched those two keys. All 1,629 unlabeled inputs
encode, but semantic span representability is still untested. The report retains
all candidates and lists every matching ID; those 46 cannot be called unseen v4
evaluation. The remaining 1,583 still require entity/alias and annotation checks.
The inherited extraction used a bounded archive prefix, trimmed strings, discarded
over-512-character values and punctuation-folded duplicates. Thus this saved pool
is a usable **limited source frame**, not an uncapped census or untouched raw source.
Do not rerun its old 250-row review selector, ASCII script heuristic or metadata
"complete" flag for the new campaign. Reuse its saved rows with these limitations;
recover raw exclusions separately if that source is expanded.

Keep three kinds of evidence separate:

- Source-sampled natural addresses: sample from an enumerated, documented source
  frame before reading model errors. Report the frame and selection probabilities
  where known. This estimates performance within that frame, not unknown user traffic.
- Targeted challenge addresses: deliberately seek floors/units, rural and landmark
  locators, PO boxes, genuine partials, repeated fields, accents and formatting noise.
  Report these separately; search-engine discoveries belong here until a sampling
  frame exists. More countries do not make a convenience sample representative.
- Rendered or deliberately corrupted examples: retain as synthetic diagnostics,
  never relabel them as naturally entered addresses or mix them into natural accuracy.

Prioritize BD/GH/ID/KE/LK/NP/PH/PK/NG/VN deficits alongside IN and the established
English-using countries. This is acquisition order, not a geographical whitelist.
Record missing countries and address types rather than satisfying them with repeated
templates. Public business premises can supply apartment/floor syntax but do not
prove residential coverage. Do not collect private individuals' home addresses to
fill that gap; use a suitably licensed, privacy-reviewed source or leave it explicit.

Before admission, reserve related domains/brands and entity aliases to one split;
perform two actual AI annotation passes and retain unresolved rows separately.
Check exact text, model-input identity, conservative street/group matches and known
entity aliases against v4 and historical protected material. A same-street hit is
not proof of the same property. Resolve candidates rather than declaring every
normalized match a duplicate. New contamination exclusions require a new training
version; do not mutate v4. Never use an annotation-status filter to hide difficult
inputs: report acquired, out-of-scope, uncertain, overlap-excluded and scored counts.

Size for the decision, not a fixed corpus cap. As a planning calculation,
`ceil(1.96² × 0.25 / margin²)` gives 385 independent observations for an approximate
95% ±5-percentage-point margin, 1,068 for ±3 points, and 2,401 for ±2 points in a
simple random sample. These are not guarantees for web convenience samples,
clustered entities, country-macro scores or systematic AI-label errors. Start with
a documented dev screen; expand toward the precision the comparison needs. A
country with only a few examples cannot pass a country-level release gate.
Freeze a separate test only after the source frame and label coverage are adequate;
keep test predictions uninspected during selection. Close model comparisons need
paired, source/entity-clustered analysis, not an aggregate margin shortcut.

Report ordered-span exact among supported scored rows **and** all scored rows with
unsupported encodings counted as failures; report the unsupported count separately.
Neither denominator includes unadjudicated labels, whose coverage must be reported
alongside accuracy. Preserve normalized field-map exact as a separate historical
comparison. Country/type/source counts and per-field span counts accompany aggregate
results. The existing training selection metric remains conditional exact until the
new evaluation membership and selection protocol are explicitly frozen.

Implemented: the shared evaluator now exposes evaluated/unsupported/total counts
and both ordered-span scores. `exact_accuracy` remains the historical supported-only
alias. For bounded supported-row samples, the all-input denominator is unknown
(`null`), because the loader's rejection count describes the full source. Tokenizer
boundary validation still fails loudly; this change does not silently swallow invalid
labels or certify every representation failure. The earlier WebGPU qualification
report is historical: its train/export source hashes precede these reporting-only
caller changes. Model, serializer and kernel behavior were not changed by this work.

The September 15 recheck of the Indian source cards confirms that the raw corpus
mixes company registrations and bank/BC records; the latter carry explicit personal
data/redaction caveats. The labeled card reports 4,825 LLM-reviewed rows and only nine
human-reviewed rows, with a different field schema. Do not bulk-admit either source
or treat its name as gold certification. Resolve privacy/reuse and remap labels first.
[Raw source card](https://huggingface.co/datasets/gagan1985/indian-addresses-raw),
[labeled source card](https://huggingface.co/datasets/gagan1985/indian-addresses-gold).

### Phase 2 — retain a large clean corpus; choose exposure separately

Follow the [data plan](address-data-plan.md). Enumerate all shards, retain useful
approved originals without arbitrary country caps, and fill measured deficits from
complementary sources. Separate physical entities from geographic holdout groups.
Split before augmentation; quarantine instead of guessing unresolved labels.

Deliverable: versioned train/dev/test inputs, original/source lineage, split groups,
rejection reasons, and one coverage report. Millions of rows are acceptable.
Incomplete country coverage does not forbid a diagnostic pilot, but it prevents a
claim that worldwide readiness has been achieved. Do not wait for unattainable
"perfect data" before learning from a valid, explicitly limited experiment.

### Phase 3 — establish the data-scale curve

1. Train a corrected H128 control on a documented slice. Preserve the historical
   checkpoint only for diagnostic comparison; the new control anchors causal tests.
2. Compare nested corpus sizes with the same scope, source-quality rules, and
   country/type exposure policy. Choose sizes after measured throughput/storage;
   do not canonize another arbitrary corpus maximum.
3. Compare at matched optimizer updates and comparable token/byte-length workload,
   reporting actual compute; then allow the larger corpus additional budget to
   test whether it needs more optimization. Epoch count alone is not a fair budget.
4. At one useful size, compare source-proportional versus balanced exposure.
   Baseline uses originals; add source-backed augmentation as a separate experiment.
5. Select using the declared natural-dev metric and country guardrails. Repeat
   close/promising comparisons, inspect learning curves, and document effect sizes,
   uncertainty, peak memory, training time, unique entities seen, and repeat exposure.

Do not run a Cartesian sweep. Each next run must distinguish two plausible
explanations of the observed errors or scale curve. Keep final test predictions
uninspected during selection.

### Phase 4 — targeted remaining errors, then browser qualification

If useful data scale and sensible optimization stop helping, identify the residual
bottleneck before considering a gap/tokenizer change, teacher, loss change, or
encoder. H192 remains parked. Correctness defects are fixes, not optional ablations.

For the selected candidate, measure float versus int8 accuracy on the same frozen
sets, ordered-frontend Python/browser parity, edge-case spans, and cold/warm browser
costs. Use the untouched final test for the release decision. A failed final test
is evidence against release, not permission to tune repeatedly against it.

The outcome must meet the declared accuracy/coverage and deployment targets together.
Do not claim that any current plan guarantees 90% or that every country is solved.

## Historical evidence retained

| Experiment | Recorded observation | Legitimate conclusion |
| --- | --- | --- |
| Unordered H128 browser baseline | 205,452 parameters; 168,001 B Brotli; 1.8 ms warm M1 median | Small custom WebGPU runtime is feasible for that model/workload. |
| Ordered H128, 100k screen | 73.30% public field-map exact versus 69.93% unordered | Ordered bytes were promising; old runtime timing does not transfer. |
| Ordered H128, 200,699 rows | 72.72% public under that run's schedule/selection | That recipe did not improve public score; not a general data-scale ceiling. |
| Ordered H128, 496,990-row mixture | 9,935/12,868 public field-map exact (77.207%); 61.2485% country macro; 5,087/6,000 generated span exact | Best selected research candidate; bounded sources, different metrics, and padding defect qualify interpretation. |
| H192 / GRU probes | Frontend / exposure confounds | Parked, not conclusively inferior or exhausted. |
| Matched 20k partial-crop screen | Control: 89/102 AI dev, 88/102 inspected test, 10,034/12,868 public. Crop: 90/102, 91/102, 9,897/12,868 | Neither promoted; crop failed the recorded gate. Not proof all partial augmentation fails. |
| Prior-checkpoint distillation probe | 81.8% to 80.0% on its 1,000-row dev slice | That short recipe failed; no general teacher/distillation verdict. |

The best historical ordered checkpoint is
`runs/ordered-byte-scan128-multisource-final-2e/best.pt`; its saved source differs
from today's package model. Evidence:
[full-data screen](evidence/ordered-byte-h128-full.json),
[multisource result](evidence/ordered-byte-h128-multisource-final.json),
[paired flips](evidence/ordered-byte-h128-paired-flips.json),
[GRU](evidence/ordered-byte-gru120-multisource.json),
[H192](evidence/ordered-byte-scan192-multisource.json),
[review/padding check](evidence/evaluate-ai-review.py),
[crop protocol](evidence/partial-continuation.py).

## Research boundaries

Real payment-address research motivates noisy-input evaluation and testing training
schedule choices; its results do not set this model's exact-match ceiling or require
a transformer teacher. The correct source is Hammami, Baligand, and Petrovski,
[Fighting crime with Transformers](https://aclanthology.org/2024.naacl-industry.17/)
(NAACL 2024), not the previously misattributed citation.

Deduplication research motivates overlap checks, not destructive punctuation folding
or removing whole streets as if they were duplicate houses.
[Lee et al., ACL 2022](https://aclanthology.org/2022.acl-long.577/)

The [GPU Time / GPU Lexer audit](gpu-reference-tooling-audit.md) and
[browser pivot evidence](webgpu-pivot.md) remain references, not proof that their
training recipes or architectures are optimal for addresses.
