# Learnings from gpu-postal

Written 16 September 2026. Research is closed; [publication remains pending](closeout.md).
This records completed experiments and decisions, not a new improvement roadmap.

## Conclusion

We built small models that train on a 16 GB M1 Pro and execute quickly in a browser.
We did not achieve dependable address parsing across the intended countries and input
styles. Worldwide Latin-script address parsing was a poor fit for our combined budget:
tiny downloads, local training, broad coverage, useful whole-address accuracy, and
limited data-curation effort.

The expensive part became obtaining and evaluating trustworthy supervision across
geographies. More rows, more repetition and a slightly larger model did not establish
a reliable route to the required quality. Closing the project is an investment decision,
not proof that small address models cannot work. WebGPU itself did not cause the
accuracy failures. We also introduced avoidable data, evaluation and implementation
problems that make a pure “model too small” explanation unjustified.

## What happened

These milestones use different datasets and metrics. They are not one accuracy curve.

| Stage | Outcome and lesson |
| --- | --- |
| GRU with ONNX/Wasm | Expanding source data improved one public benchmark from 9,743/12,868 to 10,010/12,868, but gains varied by country. Source-holdout improvement was much larger than public transfer. Runtime overhead also mattered beyond weight size. |
| Custom WebGPU pivot | We replaced the GRU path with a compact scan-based model and runtime. Small artifacts and working GPU execution were feasible; neither established parsing quality. |
| Larger, rebalanced corpus | We retained much more data and addressed country imbalance. Presentation counts still obscured unique examples, address completeness and source diversity. |
| Failure diagnosis and case augmentation | One model scored 175/2,233 on original US inputs and 1,803/2,233 after uppercasing those same inputs. A basic train/evaluation style mismatch outweighed many proposed sophisticated changes. |
| Seven-field contract | Remapping existing predictions recovered 230 public matches without changing weights. Some of our error budget had been spent on distinctions the product did not need. |
| Controlled India addition | The new batch improved fresh India agreement from 34/168 to 35/168, with regressions elsewhere. We rejected promotion and subsequently closed research. |

Sources: [source audit](address-source-quality-audit.md), [WebGPU pivot](webgpu-pivot.md),
[assumptions audit](address-next-research-plan.md), [casing diagnosis](evidence/balanced-v5-diagnosis-20260915.md),
[seven-field rescore](evidence/seven-label-rescore-20260916.md),
[final India experiment](evidence/seven-india-experiment-20260916.md).

## Why the domain was difficult under our constraints

### Latin script did not make the task geographically narrow

The intended scope included English-style addresses and addresses anywhere written
in Latin script, including local street and city names. This still required handling
different administrative hierarchies, missing components, apartments, landmarks,
rural forms, abbreviations and ambiguous proper names. A word's role could depend
on geography or surrounding components rather than its spelling.

Our scope was extraction of supplied text, not filling missing fields from metadata
or validating geography. Nevertheless, knowing whether a phrase denotes a locality,
city or district can require geographical knowledge. A small byte model trained from
scratch had to learn useful distinctions from uneven examples. Limited capacity is a
plausible constraint, but our experiments did not isolate a capacity ceiling.
[Scope and representation audit](address-next-research-plan.md).

### Supervision was a substantial part of the problem

Sources disagreed about field meanings. Indian house-number fields could legitimately
contain flat, room, shop or floor descriptions; mechanically rejecting those terms
would discard useful addresses. Other rows contained genuine boundary errors or
administrative fragments rather than full delivery addresses. A valid schema and
valid character offsets could not distinguish these cases.

The final projected India tranche carried review statuses and passed structural
checks. Reviewing all 253 rows still produced 40 boundary corrections and 21 holds.
Fresh evaluation annotations also required corrections before predictions were run.
Using AI for curation reduced manual work but did not remove the need to audit its
semantics. We had no cheap, consistently trustworthy labeling oracle for this scope.
[Annotation policy](address-annotation-policy.md),
[observed corrections](evidence/seven-india-experiment-20260916.md).

### Useful quality required more than plausible-looking tokens

An address can look mostly correct while assigning its city or postcode incorrectly.
Our whole-address agreement metrics exposed failures that high source-development
scores concealed. On the final fresh India business-address sample, the control and
treatment achieved 20.2% and 20.8% agreement; libpostal-Senzing achieved 33.9% under
the same seven-field metric. These were AI-reviewed convenience samples, not an
estimate of nationwide accuracy. They showed that neither our model nor that baseline
provided a reliable answer on this particular diagnostic.

We also lacked representative user-traffic evaluation or a user study showing value
despite errors. The evidence supported stopping this project, not asserting that
address parsing has no useful small-model applications.
[Final comparison and limitations](evidence/seven-india-experiment-20260916.md).

## Mistakes we should not repeat

### 1. We treated available rows as useful diversity

Early downloads used byte prefixes, first shards and per-country caps for convenience.
One 25,000-row OpenAddresses prefix contained only Mexican addresses. An early India
sample had only 337 house-number-bearing rows out of 12,000. Later staging inspection
classified 578,290 of 626,475 India candidates as administrative-only fragments, about
92.3%. These are different audits, but all show why row totals were poor coverage
proxies. [Initial audit](address-source-quality-audit.md),
[later corpus counts](evidence/corpus-audit-20260915.json).

Some acquisition limits became training limits without an ablation. Country quotas,
street-group caps and deduplication rules were heuristics, not demonstrated optima.
Grouping by road and city could remove distinct premises; lossy text normalization
could collapse meaningful punctuation. The balanced-v5 training mix contained
4,343,094 presentations from 2,060,208 unique pool rows, not 4.3 million distinct
physical addresses. Large raw India sources were not equivalent to millions of
reliably labeled examples. [Assumptions and corpus audit](address-next-research-plan.md).

The last experiment made this especially clear: its 259 new inputs were 90.7% Assam.
Filling 6,400 training slots repeated each input 24–25 times. That increased exposure,
not geographic diversity. It yielded one net fresh-set match and lost 24 matches on
the public diagnostic. The result rejects that recipe; it does not establish that
substantially better India data would fail.
[Matched experiment](evidence/seven-india-experiment-20260916.md).

**Next-project rule:** count unique entities, sources, regions and task-relevant input
forms separately from generated variants and training presentations. Treat sampling
caps as provisional cost controls, with their exclusions visible.

### 2. We defined the useful output contract too late

We initially trained 20 fields, including premise-level distinctions the user did not
need. Moving to seven fields improved agreement through a simpler task definition,
not newly acquired model skill. We kept city and district separate because they can
describe different administrative levels; simplification should not invent equivalence.

Training a new seven-field head then introduced a fresh comparison problem: short
encoder-transfer training improved US/UK but regressed South Africa/New Zealand.
The smaller head reduced parameter count by only about 3.1%, from 159,308 to 154,446.
It was chiefly a product-contract improvement, not a major size breakthrough.
[Matched rescore](evidence/seven-label-rescore-20260916.md),
[new-head results](evidence/seven-india-experiment-20260916.md).

**Next-project rule:** settle useful outputs and ambiguous examples before investing
in corpus conversion. Rescore saved predictions first when considering label merges.

### 3. We let favorable evaluation slices provide too much reassurance

Source-development data could reward familiar templates while fresh inputs failed.
Early development sets were sometimes extremely small. A reviewed natural-address
collection was dominated by partial inputs; the later 55-row priority slice was
mostly US. Repeatedly inspecting public benchmarks made them development evidence,
not untouched release tests. Neither a US-heavy aggregate nor an equal-country
average over tiny samples represented expected production traffic.

Metric changes also mattered. Ordered spans, normalized field strings and field-token
multisets answer different questions. The seven-field token metric ignores within-field
order and some formatting; it does not certify exact spans. Comparing old string scores
directly with new token scores would exaggerate the benefit of label merging.
Deepparse's narrower output schema prevented a fair full-contract comparison.
[Evaluation audit](address-next-research-plan.md),
[metric controls](evidence/seven-label-rescore-20260916.md),
[competitor comparison](evidence/competitor-comparison-20260916.md).

**Next-project rule:** define the acceptance metric and intended input distribution
up front, keep source/entity-separated evaluation, and label inspected tests as
development evidence. Publish denominators, paired failures and schema differences.

### 4. Basic invariance and implementation errors competed with model research

The casing failure was avoidable: augmentation code existed, but the actual training
path did not apply it. An uppercase-only workaround would also have broken previously
correct cases. Diagnosis, followed by training with the intended variation, was more
informative than immediately increasing model size.

We also found nonzero padding behavior that changed logits with batch padding,
tokenizer limits that prevented boundaries inside concatenated strings such as
`Delhi110001`, and an evaluation migration path comparing seven-field predictions
against old twenty-field gold. These were distinct failures requiring distinct fixes.
They make older headline scores unsuitable as clean capacity comparisons.
[Casing evidence](evidence/balanced-v5-diagnosis-20260915.md),
[padding/tokenizer audit](address-next-research-plan.md),
[scoring migration](evidence/seven-india-experiment-20260916.md).

**Next-project rule:** test casing, spacing, Unicode, padding independence and label
representability early. Check the exact path used by training and deployment, not
merely whether a helper or test exists somewhere in the repository.

### 5. We considered too many directions before establishing clean comparisons

Capacity increases, teacher supervision, augmentation and corpus expansion were all
plausible. Several historical comparisons changed more than one factor or used only
one seed and schedule. A failed distillation recipe did not rule out teachers, and a
modest larger-model gain did not establish the optimum architecture. We did not
exhaust the research space, and exhaustion was not necessary to justify stopping.

The final paired India comparison was a better pattern: shared parent, update count,
country counts and settings, with the replacement data isolated. Its small gain and
country regressions gave us a concrete reason not to scale that batch.
[Historical experiment limitations](address-next-research-plan.md),
[paired protocol](evidence/seven-india-experiment-20260916.md).

**Next-project rule:** use one bounded experiment to answer one decision. Set a time
budget and stopping criteria before starting; do not interpret every weak result as
a request for another dataset, model family or research survey.

### 6. Our research history was harder to preserve than it should have been

At closeout, Git contained one initialization commit, while much of the actual history
lived in uncommitted documents and local `data/` and `runs/` directories excluded from
Git. Several historical documents described different models as “current.” A checkpoint
name, repository tag or successful test suite alone did not identify a reproducible
release.

**Next-project rule:** retain a small manifest with checkpoint hash, source snapshot,
data identity, label contract, metric and export version for each consequential result.
Archive selected evidence deliberately. A weights file and its matching runtime must
travel together. [Closeout preservation plan](closeout.md).

## What worked, and what WebGPU did not solve

Local training was viable. A recorded throughput probe measured about 154 rows/second
on CPU at batch 64, 1,170 on MPS at batch 64 and 1,738 on MPS at batch 128. This was
a bounded probe, not sustained end-to-end throughput; it included tensorization but
not the full shuffled disk-loading loop. Streaming preparation avoided requiring the
whole expanded corpus in memory. Plain PyTorch and a single Python environment were
adequate. More training-framework machinery was not the missing ingredient.
[Throughput evidence](evidence/retraining-throughput-20260915.json),
[implementation notes](../README.md).

The seven-field baseline exported to 128,462 Brotli-compressed bytes and passed 29
JavaScript and actual WebGPU parity fixtures. Its int8-storage artifact measured a
2.5 ms warm median on mixed fixtures. Those measurements belong to that baseline,
not the older checkpoint nominated for publication. The GPU executes dequantized
float32 weights; “int8” describes storage here, not integer GPU arithmetic.
[Exact baseline measurements](evidence/seven-india-experiment-20260916.md),
[runtime design](webgpu-pivot.md).

WebGPU helped execute the learned function locally. It could not supply missing
geographic knowledge, repair source labels or make the function generalize. We also
did not demonstrate an end-to-end advantage over a good CPU implementation for a
single short address, including cold start. The September 14 reference audit found
that GPU Time itself selected CPU for small jobs. GPU Lexer had a reference highlighter
for supervision; GPU Time used generated frames and reference parsing. Their success
did not imply equally cheap supervision for worldwide addresses, or require us to
copy a presumed pretrained-model recipe.
[Pinned GPU Lexer / GPU Time audit](gpu-reference-tooling-audit.md).

## How to choose the next small browser-model project

Before building a custom GPU runtime, establish:

1. A stable output contract and a useful success criterion for real inputs.
2. A cheap, auditable source of labels or reference outputs, including difficult cases.
3. Evidence that the task does not require broad, changing factual knowledge absent
   from the input and training data.
4. A small baseline that transfers across sources, rather than only matching generated
   or familiar templates.
5. A credible advantage from local execution, measured against CPU execution for the
   expected workload, including download and cold-start costs.
6. A bounded experiment budget with an explicit decision to continue or stop.

For this project, we demonstrated compact local execution and local trainability.
We did not demonstrate the supervision coverage, cross-source reliability or product
value needed to justify continued investment. Preserve the result and its limitations;
do not turn this retrospective into another training plan.

## Evidence boundary

This account uses the retained September 14–16 reports, local artifacts and project
conversation. Ratios above were recomputed from their recorded counts. It is not an
independent rerun or a new external literature review. AI-reviewed labels, benchmark
exposure, small country samples and single-seed experiments limit the conclusions.
Historical proposals are cited as proposals or identified limitations, not completed
experiments. No claim here establishes a universal model-size lower bound, failure
of all distillation methods, or inability to train useful models on a Mac.
