# Closeout and publication plan

**Superseded for active work:** the user reopened a narrower seven-country training
and publication effort on 16 September 2026. Follow [that plan](english-seven-release.md).
This document preserves the previous closeout decision; its no-training and archive
instructions are not active while the new run is underway.

Decision: 16 September 2026. **Research closed; publication pending.**
This supersedes every active data-acquisition, training and improvement roadmap.

## What we are publishing

A small, reproducible WebGPU address-parsing research result, not a production
address validator or a libpostal replacement. Stop new training, annotation,
source hunting and architecture experiments. Preserve the work already completed.

The conclusion is that this project did not meet its required accuracy/coverage
within the chosen size and effort budget. The experiments do not establish an
impossibility result for small address models generally.

## 1. Freeze one primary candidate

Nominate `runs/ordered-h128-case-v6-scratch-20260915/epoch-1.pt`, SHA-256
`fb3d3c0bd74eb697ebb77372e2b7be8182e5f876261516813f21978ce30bd8bd`.
It has 159,308 parameters and the corrected ordered H128 v2 architecture.

Selection criterion: balanced performance across the five stated priority countries
(US, UK, ZA, NZ, India), rather than a US-dominated aggregate. In the recent matched
seven-field rescore, their unweighted public-country mean is 77.56% for this candidate
versus 72.20% for the seven-label control. These small, previously inspected public
slices are diagnostic evidence, not country-wide accuracy or unbiased selection.

There is no universal winner: the control is better on US/UK and fresh India, while
case-v6 is substantially better on ZA/NZ. Preserve that comparison and the older
historical results in the report; do not describe this nomination as winning every
metric or compare confounded historical headline scores as if they were equivalent.
Do not ship an ensemble or maintain multiple runtime variants.

This candidate has **20 internal fields / 41 BIO tags**, not the current 15-tag
seven-field head. Keep its learned weights unchanged. Expose the agreed seven fields
through a fixed output projection and adjacent-span merge; do not retrain just for
label simplification. Restore/reuse the matching GPA2 exporter/runtime for this
release, not a GPA3 header on incompatible tensors. Pin the matching training source
snapshot. This packaging work is pending, not already implemented.

## 2. One release qualification pass

- Produce matching float32 and int8 browser artifacts and minimal loading example.
- Run existing Python/JS contract tests and real-WebGPU parity for these exact weights,
  including seven-field projection and Unicode offsets.
- Measure this candidate's bytes and warm runtime; assess int8 versus float on the
  same existing frozen diagnostics. Publish both scores and any quantization loss.
- Do not reuse the newer seven-head model's 128 KB / 2.5 ms measurements as this
  candidate's measurements. No new benchmark collection or hyperparameter search.
- If int8 changes quality materially, publish the float artifact as the default and
  label int8 experimental. If a matching browser artifact cannot pass correctness
  checks, publish the checkpoint/source/report with the browser limitation explicit;
  do not hide the failure or restart model research.

## 3. Package the evidence once

Prepare a single research release on the existing `f0rr0/gpu-postal` GitHub repository:

- A compact README/model card: intended Latin-script scope, seven public fields,
  unsupported inputs, no validation/confidence guarantee, country/source limitations.
- One results table with denominators, metric definitions, old/new comparisons and
  Senzing context. Include weak India/Australia performance, country regressions,
  AI-reviewed labels and benchmark exposure; do not advertise a single global accuracy.
- Primary checkpoint, matching source/runtime/export, checksums and reproduction commands.
  Keep the losing experiments as evidence, not extra supported products.
- The [project retrospective](learnings.md): what worked (tiny WebGPU execution),
  what did not (consistent parsing accuracy across sources/countries), our process
  mistakes, and why investment stopped. Written locally; publication remains pending.

Important preservation step: `data/` and `runs/` are gitignored. A Git tag alone does
not save weights, manifests or local predictions. Retain a local backup of evidence
and attach the selected redistributable artifacts to the release. Do not upload the
raw address corpora or every local file. Review selected files for private data and
third-party redistribution restrictions first; publish hashes/aggregate evidence
and acquisition instructions where redistribution is unsuitable.

No root LICENSE was found during this closeout inspection. Resolve the code and
weight licensing notices before public distribution; do not invent permission.
The existing worktree contains substantial unrelated/uncommitted history: stage
deliberately, preserve it, and do not use a broad cleanup/reset.

## 4. Publish, then archive

Use one manual GitHub research release, with a conventional commit/tag after the
artifact and documentation checks. No new release workflow, website, Python wheel,
model registry integration or ongoing service. An npm publication is not necessary
for this closeout; do it only if explicitly wanted, using the same qualified artifact.

After publication, mark the README as archived research, link the immutable release,
and archive the GitHub repository read-only. Do not delete local datasets/checkpoints
or archive the repository before attaching the release. No maintenance or accuracy
improvement roadmap remains.

## Completion checklist

- [x] Close research and supersede further-training plans.
- [x] Nominate a primary checkpoint and document the selection tradeoff.
- [x] Record experiment history and project learnings.
- [ ] Freeze a matching seven-output browser package and qualify the exact artifact.
- [ ] Resolve licenses and preserve selected local-only evidence.
- [ ] Publish the research release and retrospective.
- [ ] Archive the repository; leave artifacts available.

This turn creates the plan and marks research closed. It does **not** publish,
push, tag, change licenses, delete artifacts or archive the remote repository.

Evidence: [seven-field rescore](evidence/seven-label-rescore-20260916.md),
[completed India comparison](evidence/seven-india-experiment-20260916.md).
