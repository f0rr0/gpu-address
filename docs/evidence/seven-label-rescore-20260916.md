# Seven-label rescore — 16 September 2026

Recommendation: adopt the simpler product contract before another training experiment, but do not call this model improvement. This run only remaps saved outputs and gold; weights, training data and the production API are unchanged.

## Results

Same per-field token-content metric in every column. Each address passes only if every field matches. H128 is case-v6 epoch 1; both epochs remain in the JSON artifact.

| Public country | Rows | H128 20 labels | H128 7 labels | Senzing 20 labels | Senzing 7 labels |
|---|---:|---:|---:|---:|---:|
| US | 2233 | 79.9% | 86.1% | 95.9% | 99.0% |
| UK | 255 | 65.9% | 86.3% | 78.4% | 95.7% |
| South Africa | 53 | 60.4% | 81.1% | 67.9% | 90.6% |
| New Zealand | 51 | 84.3% | 84.3% | 98.0% | 100.0% |
| India | 54 | 18.5% | 50.0% | 44.4% | 59.3% |
| Australia | 76 | 28.9% | 31.6% | 98.7% | 100.0% |
| Singapore | 50 | 78.0% | 98.0% | 98.0% | 100.0% |

Do not extrapolate these small or previously exposed public slices to country-wide accuracy.

Separate diagnostics:

- India pilot, 359 rows: H128 **48 → 61** correct (13.4% → 17.0%); Senzing **49 → 65** (13.6% → 18.1%).
- Natural priority subset, 55 rows: H128 **43 → 47** (78.2% → 85.5%); Senzing **46 → 48** (83.6% → 87.3%). Mostly US, not a balanced country sample.
- Public 2772-row slice: merging alone recovers **230** H128 and **137** Senzing cases. No rows were excluded.
- H128 epoch 2 reaches 2298/2772, versus epoch 1's 2328/2772. Epoch 2 is slightly better in US/UK but worse in several other countries; retain both results rather than selecting a checkpoint per country.

## Mapping used identically for predictions and gold

- `street_address`: house, house_number, road, unit, level, staircase, entrance, po_box, near.
- `locality`: suburb, city_district, island.
- `city`: city.
- `district`: state_district.
- `state`: state, country_region.
- `postcode`: postcode.
- `country`: country.
- category and world_region: outside the proposed address fields. There are two category gold components and no world_region components. There are no island or country_region gold components, so their policy is not validated here. Predicted islands remain scored as locality, not discarded.

Island → locality and country_region → state are provisional coarse administrative buckets, not claims of geographic equivalence. Before production migration, explicitly define those rare cases. `near` is retained in street_address; this static rescore does not move landmark targets based on relational context. A full landmark phrase may need span-level annotation updates when its target was labeled city/locality. Do not claim the final landmark contract has been evaluated here.

## Scoring and checks

Public gold is often grouped by field rather than source order. Comparing newly concatenated strings in that stored order would create artificial failures. This diagnostic therefore compares **token multisets per field**, retaining repeated-token counts and punctuation except commas, after NFKC/casefold. It ignores within-field order, commas and whitespace. It does not certify exact original spans, punctuation preservation, or output ordering.

The 20-label control uses the identical token metric. This separates label simplification from normalization gains: H128 public original field-string exact was 2095; token control is 2098; seven-label token exact is 2328. Senzing is 2567 → 2575 → 2712. Do not compare seven-label results directly to the earlier string metric and attribute all improvement to merging.

All 3186 input IDs were matched once per model. Assertions check the user's apartment/floor/building example, preservation of city-versus-state errors and duplicate-token differences, and that fine-token matches cannot become coarse-token failures. Unknown labels fail instead of being silently dropped. Source/prediction/script hashes and paired remapped field-token contents are saved.

The data-quality checks influenced the use of a matched 20-label scoring control and explicit rare-label policy. Existing benchmark exposure, AI-reviewed pilot labels, one repeated input text, and unequal country sample sizes still apply. Deepparse is omitted because it cannot express the proposed complete seven-field contract.

## Next step

Migrate the training/output contract to these seven fields, preserving original text and merging adjacent spans correctly; retain original detailed annotations as source evidence. Then run one controlled seven-label training comparison before changing architecture or sourcing more data. This requires new weights: old 41-tag weights must not be loaded against a 15-tag schema.

Remaining H128 public mismatches involve city in 404 rows and state in 269; only 92 involve street_address. Counts overlap. India pilot still has 239 city, 215 street_address and 204 district mismatches. The simplified schema helps, but neither larger models nor label merging alone has been shown to solve these errors.

Reproduce: `uv run python docs/evidence/compare-parsers-20260916.py score-seven`. Outputs refuse overwrites. Artifacts: `data/competitor-comparison-20260916/seven-label-scores.json` and `seven-label-paired.jsonl`. No new dependencies or training runs.
