# Project ideas for tiny browser models

This document explores the narrower parser-oriented candidates. For the current priorities across image, text, document, and interaction primitives, see [Frontend opportunities](webdev-opportunities.md).

## Recommendation within this parser-oriented set

Start by testing **Measure**, a parser for quantities and measurements in short text. It has the closest relationship to gpu-time: predict spans and roles, then let ordinary code interpret numbers and units. Existing parsers provide baselines and potential supervision, while ambiguity gives a learned component something useful to attempt.[^1][^2][^3]

**Paste** is the most distinctive demo: messy text becomes an editable table. Its first challenge is establishing a useful problem beyond ordinary CSV/TSV parsing. **Fields** is the strongest option for a reusable data-import library, with semantic column typing as its narrow prediction task.[^4][^5][^6]

These are proposals, not discoveries of unoccupied markets. Existing work validates the tasks and supplies benchmarks; it also raises the bar for building another implementation. Browser size and local execution are possible differentiators, not established advantages until measured.

## Selection criteria

A good candidate has a compact output, cheap inputs, obtainable labels, a useful deterministic consumer, and an obvious way to show mistakes. Its learned judgment should matter on real examples that a reasonable baseline struggles with.

| Proposal | User-visible result | Training-data path | Main uncertainty | Assessment |
| --- | --- | --- | --- | --- |
| Measure | Measurements become structured quantities | Semantic generation, existing parsers, manually checked real text | Benefit beyond a compact grammar | Best initial experiment |
| Paste | Messy table text becomes editable cells | Render known tables; annotate real clipboard samples | Real paste failures and irreversible loss of layout | Most distinctive demo |
| Fields | CSV columns receive suggested semantic types | Public tables, header-derived weak labels, reviewed labels | Ambiguity and source leakage | Strong developer utility |
| Ingredients | Ingredient lines become amounts, items, and preparation notes | Existing labeled corpora and parser teachers | Achieving a small runtime without losing grouping accuracy | Best alternate for accessible supervision |
| Read | A page yields its actual article blocks | Existing extractors, labeled pages, DOM perturbations | Existing Readability is already strong | Useful, competitive |
| Reply | Email reply, quote, and signature are separated | Public annotated mail, synthetic threads, consented samples | Inline replies and representative data | Useful, harder data problem |
| Filters | Search text becomes visible filter chips | Generate from one fixed search schema | Broad wording and changing schemas | Promising only with a specific host app |

The following example outputs and model designs are proposed contracts, not outputs measured from implemented models. M1 feasibility applies to the proposed small architectures, not to reproducing every cited project.

## 1. Measure: quantities and measurements

### The experience

```text
“between 2 and 3 kg”       → range: 2–3; unit: kilogram
“under half a litre”      → upper bound: 0.5; unit: litre; exclusive
“two 500 ml bottles”      → count: 2; per-item volume: 500 ml
“a five-pound bag”        → mass: 5 lb
“I spent five pounds”     → currency meaning; unsupported by a mass-only parser
“Model 500 XL”            → no measurement
```

Potential hosts include shopping-list editors, product specification forms, inventory imports, and unit-aware search. Highlighting the recognized pieces while typing gives an immediate demo.

### Learned task and deterministic task

Predict roles such as number, fraction, unit, range connector, comparison, container count, and other. Add a compact relation or grouping prediction only if needed to connect a count with its per-item quantity. Code parses numbers, resolves the selected unit, applies exact conversions, and preserves original spans.

The interesting cases are context and attachment: pounds as currency or mass, counts versus measurements, a range versus two independent quantities. An inherently ambiguous input such as a bare “12 oz” may need a field hint or an ambiguity result. A model cannot recover intent absent from the text.

### Data and precedent

Generate a known quantity structure and render spelling, fractions, punctuation, order, and units in different ways. Use independently checked real product and recipe phrases to reveal generator blind spots. Quantulum3 already combines quantity extraction with a trainable unit-disambiguation classifier; Duckling and Microsoft Recognizers-Text supply additional baselines.[^1][^2][^3]

Agreement between these tools can produce weak labels, but their outputs must be normalized to the same unit and grouping policy. Disagreements are valuable annotation candidates. Keep examples involving identifiers, prices, dates, and ordinary prose as negatives for the chosen scope.

### Feasibility and test

A small token tagger is a reasonable M1 experiment. A provisional range of 50,000–250,000 parameters is an exploration budget, not a size prediction. Begin with English, explicit locale, and a short unit list. Compound rates, dimensions, and pack sizes can be evaluated as separate extensions.

Compare exact extracted structures and false positives against a compact grammar. Stop if the learned model adds little on independent real text and offers no meaningful packaging advantage. The [first experiment](first-experiment.md) makes that decision concrete.

## 2. Paste: recover tables from messy text

### The experience

Someone copies a table from a terminal, document, or webpage and pastes it into a spreadsheet-like UI:

```text
Item             Qty   Unit price
USB C cable       2      9.99
Laptop stand      1     39.00
```

The library proposes three columns, marks the header, and previews the cells. Original character ranges remain available so the UI can show exactly what it interpreted.

### Learned task and deterministic task

Use a model to rank candidate layouts or classify separators and row roles. Inputs include whitespace-run widths, alignment across rows, punctuation, numeric patterns, and neighboring rows. A deterministic parser constructs cells from the selected layout.

Candidate ranking is an attractive first design: it is easier to inspect than generating a table. Its limitation is explicit—the correct layout must occur among the candidates. A boundary tagger is a later option if candidate recall is the bottleneck.

Do not ask a model to invent missing cells or reconstruct information lost during copying. Unknown layouts should produce a preview requiring correction or remain plain text.

### Data and precedent

Start from known tables and render fixed-width, delimiter-separated, Markdown, and noisy versions. Labels follow directly from rendering. Split underlying tables and renderer families before augmentation, so the model cannot succeed merely by recognizing the same table with different spacing.

Papa Parse already provides browser CSV parsing and delimiter detection. CleverCSV studies messy CSV dialect detection. Both are serious baselines; valid CSV, TSV, and clipboard HTML tables should use their existing structure directly.[^4][^5]

### Feasibility and test

A small candidate-ranking network using row/column statistics should be trainable locally. Start with plain-text tables that preserve separators or alignment. Wrapped cells, OCR, PDFs, and arbitrary two-dimensional document reconstruction are outside version one.

Collect 100 varied real paste failures before training. If a deterministic candidate scorer fixes almost all of them, ship that scorer and reconsider the model. Evaluate exact table structure, unchanged cell contents, non-table rejection, and performance on unseen source applications.

This has the largest demo appeal in the shortlist, but less evidence of a ready-to-use representative labeled corpus than Ingredients or Fields.

## 3. Fields: semantic types for imported columns

### The experience

```text
Header “mail”, sample values       → email
Header “zip”, values with zeros    → postal_code; preserve as strings
Header “renewal”, date-like values → date candidate; locale unresolved
Header “code”, mixed identifiers   → identifier or unknown
```

A CSV import wizard suggests types and appropriate controls. It can protect postal codes from numeric coercion and reduce repetitive mapping work. It should show suggestions before changing values.

### Learned task and deterministic task

Classify a column from its header and a small sample of values. Features could combine character n-grams, null rates, uniqueness, length distributions, and successful matches from deterministic validators. A shared value encoder with pooling makes the representation independent of row order.

Start with perhaps 10–15 types: email, URL, phone-like string, postal code, date-like string, currency amount, percentage, identifier, boolean, numeric measure, free text, and unknown. Predicting an application-specific destination such as “billing contact” is a separate schema-matching task.

### Data and precedent

Sherlock provides research and code for semantic column classification; its paper uses 686,765 columns and 78 semantic types. This supports the task, not the claim that its original model is tiny or that its whole dataset is necessary.[^6]

Header-derived labels are weak supervision. Human-check the evaluation set, include absent/misleading headers, and hold out whole tables and source domains. Duplicate exports of one table must stay in the same split.

### Feasibility and test

A narrow classifier over compact statistics and hashed text features is feasible to investigate on the M1. Begin by comparing it with regex validators plus a header dictionary. Measure accepted-prediction precision, coverage, and confusion between identifiers, numbers, dates, and postal codes.

If a column could be either an account ID or a postal code, the correct product behavior may be “unknown.” Stop if useful coverage requires silently guessing semantics that the supplied samples cannot determine. Large batches of columns offer a more plausible GPU use case than a single short phrase, but still require measurement.

## 4. Ingredients: a structured recipe-line parser

```text
“2 x 400 g cans chopped tomatoes, drained”
  → count: 2; per-container amount: 400 g
  → ingredient: chopped tomatoes; preparation: drained
```

This could power recipe imports, shopping lists, and serving adjustments. A tagger predicts amount, unit, name, preparation, and comment spans; code preserves the name, groups quantities, and performs explicit arithmetic. Ingredient identity matching and nutrition lookup remain separate problems.

The NYT released human-labeled ingredient phrases and CRF code. The maintained Ingredient Parser project documents datasets, features, training, and postprocessing. A historical JavaScript port, ingreedy-js, demonstrates that browser/JavaScript ingredient parsing is not new; the opportunity would be a modern, small, well-evaluated package.[^7][^8][^9]

This is a strong learning project because it has natural language, constrained labels, and accessible supervision. Check the terms and provenance of each dataset before choosing the distributable training corpus; a repository's code license does not by itself establish every data right.

Hold out recipe/source groups and score whole-line structures. Pay special attention to nested quantities, ingredient alternatives, ranges, and fractions. Never infer mass from volume without an explicit ingredient-specific conversion. Stop if a CRF or an existing parser port satisfies the desired footprint and accuracy with less work.

## 5. Read: select the actual content of a page

A browser extension highlights article paragraphs while excluding navigation, related links, and repeated page furniture. This could feed a reader view, clipping tool, or local search index.

A small block classifier would use DOM depth, tag and class-name hashes, text/link density, length, and neighboring blocks. Code returns original nodes or text spans. Start with article-body versus boilerplate; titles and bylines add separate labels and error modes.

Mozilla Readability is an existing browser-native baseline. Web2Text demonstrates neural scoring of DOM-derived features followed by structured decoding, with code and a CleanEval evaluation.[^10][^11]

Distill extractor outputs for scale, then independently annotate disagreements. Hold out entire sites and templates; otherwise the model can memorize a site's structure. Old benchmark success is insufficient evidence for contemporary web layouts.

M1 model training is plausible, but collecting and labeling varied pages is the larger burden. Evaluate article-text precision/recall and lost paragraphs. Stop if Readability is already sufficient on the intended sites. WebGPU could easily add overhead because DOM traversal remains CPU work.

## 6. Reply: separate new email text from history

A mail or support UI highlights the newly written answer and collapses quoted history and signatures. A proposed line tagger predicts reply, quote, signature, header, or unknown. Features include indentation, quotation markers, signature patterns, sender matches, and neighboring lines.

Mailgun Talon already combines quotation handling, heuristic signature extraction, and SVM-based signature classification. Its documentation links an annotated email dataset and explains retraining.[^12]

Synthetic reply chains offer controlled labels, but real client formatting and inline replies require independently annotated mail. Hold out senders and conversations. Use only public or explicitly contributed samples for a shareable dataset.

The key metric is retaining newly written content, especially answers inserted inside a quote. A reversible collapsed preview is a better first application than deleting text before downstream processing. Stop if the training set cannot cover the target clients or languages. The network can be small; representative data is the hard part.

## 7. Filters: turn search phrases into inspectable filter chips

```text
“open bugs assigned to me”
  → status: open; type: bug; assignee: current user
```

This belongs in one specific issue tracker, file manager, or catalogue. The model tags operators, fields, and literal spans against a fixed schema; code validates them and builds the query. A visible filter preview lets a person catch misinterpretation before searching.

Generate utterances from valid query trees and collect real searches with independently checked meanings. Hold out paraphrase/template families. Compare against aliases plus a conventional query grammar.

This is an exploratory proposal with less direct compact-model evidence in this investigation. It becomes a much harder task if expected to understand arbitrary schemas, unrestricted synonyms, or implicit business concepts. A restricted classifier is a plausible M1 project; broad tool calling belongs closer to the Needle 2 approach described in the [full research](research.md).

Stop if the host app has no repeated natural-language search friction. Do not build a general query framework before identifying one fixed useful contract.

## Projects to defer

- **General PII redaction:** existing small models are available, and missed entities make a weak first model hard to deploy responsibly. An assistive highlighter would have a more manageable contract.
- **Universal address parsing:** libpostal demonstrates the scale of multilingual address variation and training data. A regional parser could be tractable, but “all addresses” is a poor initial scope.[^13]
- **JSON repair:** valid syntax has deterministic parsers; malformed text often does not encode a uniquely correct intended structure.
- **General grammar correction or summarization:** open-ended outputs move away from the small labeling task that makes gpu-lexer and gpu-time attractive.
- **A model whose only claim is GPU acceleration:** short strings may be dominated by dispatch, compilation, and readback overhead. Product value must survive a CPU comparison.

## Where to begin

Choose **Measure** for the closest gpu-time-like experiment, **Paste** for the most distinctive interaction, **Fields** for data-import utility, or **Ingredients** for an established labeled-data path.

Before committing to a full project, produce one compact evaluation corpus and baseline comparison for the selected idea. The first valuable result is evidence that the narrow learned judgment improves the chosen workflow. Custom shader engineering comes after that result.

## Sources

Primary sources checked September 14, 2026. Counts and capabilities below describe cited projects, not proposed implementations.

[^1]: Quantulum3 contributors. [Repository, disambiguation and training documentation](https://github.com/nielstron/quantulum3).
[^2]: Meta. [Duckling: supported dimensions and parsing examples](https://github.com/facebook/duckling).
[^3]: Microsoft. [Recognizers-Text](https://github.com/microsoft/Recognizers-Text).
[^4]: Papa Parse. [Documentation: parsing, delimiter detection, and configuration](https://www.papaparse.com/docs).
[^5]: Alan Turing Institute. [CleverCSV](https://github.com/alan-turing-institute/CleverCSV). Van den Burg et al. [Wrangling Messy CSV Files by Detecting Row and Type Patterns](https://arxiv.org/abs/1811.11242), 2018.
[^6]: Hulsebos et al. [Sherlock: A Deep Learning Approach to Semantic Data Type Detection](https://arxiv.org/abs/1905.10688), 2019. [Code and data](https://github.com/mitmedialab/sherlock-project).
[^7]: The New York Times. [Ingredient phrase tagger](https://github.com/nytimes/ingredient-phrase-tagger).
[^8]: Ingredient Parser. [Training data](https://ingredient-parser.readthedocs.io/en/latest/explanation/data.html), [model training](https://ingredient-parser.readthedocs.io/en/latest/explanation/training.html), and [repository](https://github.com/strangetom/ingredient-parser).
[^9]: Tom White. [ingreedy-js](https://github.com/tomwhite/ingreedy-js).
[^10]: Mozilla. [Readability](https://github.com/mozilla/readability).
[^11]: Vogels et al. [Web2Text: Deep Structured Boilerplate Removal](https://arxiv.org/abs/1801.02607), 2018. [Repository](https://github.com/dalab/web2text).
[^12]: Mailgun. [Talon: quotation/signature extraction and classifier training](https://github.com/mailgun/talon).
[^13]: OpenVenues. [libpostal: international address parsing and training-data generation](https://github.com/openvenues/libpostal).
