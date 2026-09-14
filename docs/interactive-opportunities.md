# Opportunities that produce executable browser behavior

## Latest correction: broad developer need comes first

The user rejected pattern search and animation as too niche; chart creation has only tentative interest. These are not current recommendations. Postal-address parsing remains a lower bar. A visually impressive demo is insufficient: the capability must be a useful dependency across a substantial category of everyday applications, comparable to date parsing or syntax highlighting.

The search should begin with an existing developer need and its integration point, then test whether a small learned component has an advantage. Inventing a natural-language interface for a specialized tool reverses that order.

### Lead A: contextual spelling suggestions as an editor primitive

**Contract:** sentence in; suspected error spans and ranked replacements out. Example: “Please bare with me” suggests “bear”; “a bare wall” remains unchanged. This is an inline checking component, not a general rewriting assistant.

**Integrations:** rich-text editors, comment composers, support tools, CMSs, and messaging interfaces. A developer controls how suggestions appear and which domain words are accepted. Native browser spellchecking is the first baseline; adding a model solely to reproduce basic misspelling underlines is not justified. [Browser spellcheck](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/spellcheck).

**Generator:** begin with clean sentences, replace selected words with known misspellings or confusable alternatives, and retain original words and spans as labels. Include unchanged sentences so the model learns to leave correct text alone. Ordinary edit-distance/dictionary logic can propose candidates; the model ranks candidates in context. Whole-word confusions can accidentally produce another valid sentence, so generated provenance alone cannot certify that every corrupted example is an error.

**Existing evidence:** NeuSpell provides word-replacement, character-perturbation, and empirically informed probabilistic noisers. Its research evaluates contextual spelling correction and reports benefits from realistic synthetic errors over random perturbations. It demonstrates the data strategy, not a gpu-lexer-sized browser solution. [Code and noisers](https://github.com/neuspell/neuspell), [paper](https://arxiv.org/abs/2010.11085).

**Deciding experiment:** contextual candidate ranking on real errors and correct sentences, with particular attention to unwanted corrections. Count the dictionary and runtime as well as weights. An English-only candidate ranker is narrower than grammar correction, but useful tiny-model quality remains unproven.

### Lead B: relevance ranking for an ordinary website search box

**Contract:** a query and a short list of candidate results in; relevance scores/order out. An illustrative desired behavior is “stop getting emails” ranking an unsubscribe/preferences page above a page about sending email. This is a target behavior, not a measured model result.

**Integrations:** docs search, help centres, knowledge bases, and in-app search. Keep indexing and first-stage retrieval deterministic. The learned component reranks a small retrieved set locally. It cannot recover a relevant result that the first stage never retrieved.

**Why this differs from the rejected pattern-search proposal:** the user uses an ordinary search box and expresses their information need. They do not learn a pattern-description interface. The problem is relevance when the user's wording differs from the content.

**Labels:** use existing query/passage relevance judgments. MS MARCO publishes a large labeled passage-ranking collection and query/positive/negative training triples. These are data for learning relevance, not a guarantee that a tiny model can acquire broad semantics. Missing relevance labels must not be treated as proof of irrelevance. [Official data description](https://github.com/microsoft/msmarco/blob/master/Datasets.md).

**Synthetic-data boundary:** keyboard mistakes, abbreviations, and dropped words can be generated with known originating strings, but that supports lexical robustness. It does not establish semantic relevance for paraphrases. If using a larger model as teacher, its scores are weak labels and need independent evaluation.

**Deciding experiment:** improve ranking over a real lexical baseline on held-out websites while keeping the entire deployable package small. Fuse already supplies fuzzy and token search, so merely handling typos is not enough. [Fuse token search](https://www.fusejs.io/token-search.html).

The product need is broad; the capacity requirement is the main obstacle. Do not promise general semantic search in tens of kilobytes, or describe this as replacing the entire search engine.

### Leads considered but not promoted

- Clipboard handling has broad relevance, but HTML/TSV clipboard payloads already preserve much of the information. GitHub's paste-markdown handles useful conversions deterministically. Learning would have to target a demonstrated failure mode, not replace ordinary clipboard parsing. [paste-markdown](https://github.github.com/paste-markdown/).
- PII span detection has broad practical applications and a concrete synthetic pipeline in Presidio Research. However, it is already represented by Desert Ant's Redact in the original research; relabeling it as a new discovery would not advance this exploration. [Presidio generator and evaluation](https://github.com/microsoft/presidio-research).

These two leads pass the breadth criterion better than the prior suggestions. Neither has yet passed the full usefulness/size/accuracy test or been accepted by the user.

## Current brief

Postal-address parsing is a lower bar, not the target. The reference quality is gpu-lexer and gpu-time: a focused learned component that turns messy input into something an application can immediately use. We want an equally clear or more compelling capability, non-vision, with bulk labels or a concrete label generator. A model should earn its place against a deterministic implementation.

Word splitting and hard-wrap repair were rejected as insufficiently useful or difficult. Citation parsing was rejected as an unexciting outcome. Font recognition is outside the current non-vision scope. Earlier documents preserve research, not an accepted shortlist.

The opportunities below are proposals, not demonstrated tiny models. Existing research establishes task/data precedents; it does not establish our achievable size, accuracy, or training time. No candidate has yet been accepted by the user.

## 1. A find box that understands patterns

**Interaction:** In a browser editor, type “whole words starting with un and ending with able.” Matching words light up. In a filename list, type “PDFs whose name contains invoice but not draft.” Matching files become selected. The reusable output is an executable matcher, plus an explanation the user can inspect.

**Focused initial contract:** one request becomes one bounded pattern over strings. Support literals, character classes, repetition counts, boundaries, ordering, alternatives, and exclusions. Keep extraction/capture groups as a subsequent extension; full-string classification and substring extraction require different labels and evaluation.

**Why useful:** gives editors, log viewers, file browsers, and data-cleaning interfaces a pattern search mode without requiring users to learn regex. The model only interprets the request once; ordinary code matches all the content. The potential benefit is a local language interface, not faster regex execution.

**Concrete label generator:** sample a small pattern tree; render both its executable predicate and multiple descriptions. Generate candidate strings and execute the predicate to obtain positive/negative examples. Preserve literal spans rather than making the model memorize filenames or quoted words. Test predicted programs on distinguishing examples and, for a compatible regular-language subset, equivalence checks.

This is a particularly strong data precedent: DeepRegex publishes paired synthetic/human-paraphrased datasets and an actual generator. Its source implements separate `logical_form()` and `description()` methods on composable nodes, and checks generated positive/negative strings by execution. Its formal dialect includes intersection/complement; it must not be copied directly as JavaScript regex. [Repository](https://github.com/nicholaslocascio/deep-regex), [generator source](https://github.com/nicholaslocascio/deep-regex/blob/master/data_generation/generate_regex_data.py).

**Where learning earns its place:** translating varied phrasing and modifier scope into the same constrained operations. A direct grammar parser is the baseline. If the model only accepts template-shaped English, shipping the parser is preferable.

**Big risk:** natural-language generalization and silent overmatching. StructuredRegex explicitly investigates the limited complexity and linguistic diversity of earlier datasets. Hold out entire description families and evaluate real requests, not merely new literal substitutions. Preview matches and allow a positive/negative example to disambiguate. [StructuredRegex paper](https://arxiv.org/abs/2005.00663), [code/data](https://github.com/xiye17/StructuredRegex), [REGEL language-plus-examples precedent](https://github.com/utopia-group/regel).

## 2. One sentence becomes a working chart

**Interaction:** Drop in a CSV and type “total revenue by country, highest first, top five.” A bar chart appears. Its controls show the selected columns, aggregation, sorting, and limit. Changing “total” to “average” updates the actual computation and chart.

**Focused initial contract:** one known table, explicit column names or developer-provided aliases, one grouping column, one measure, count/sum/mean, sorting, and a limit. Start with a bar chart. No joins, business-metric inference, arbitrary SQL, or conversational context required. Filtering can be a later operator; it need not inflate the first experiment.

**Why useful:** embeddable chart creation in dashboards, spreadsheets, CSV tools, and reporting products. The model supplies the interpretation; the application executes aggregation and renders the result. This could avoid an inference request for a common, tightly scoped interaction. It does not replace the chart renderer or make chart rendering cheaper.

**Concrete label generator:** sample a table schema and a valid chart/query specification. Render several descriptions from the specification, inserting column names and preserving their identities. Execute the specification against generated tables to label the resulting data as well as the intended operations. Randomize names and hold out schemas to test whether the model learns operators rather than a fixed sales vocabulary.

For example, the same known specification can render as “sum revenue for each country,” “countries ranked by total revenue,” or “total revenue grouped by country.” These phrases are authored generator rules with known semantics; an LLM is not supplying the ground truth.

**Existing evidence:** nvBench provides 25,750 natural-language/visualization pairs across 105 domains and seven visualization types, including Vega-Lite representations. It is a broader, synthesized benchmark, useful as a data/operation reference rather than proof that our restricted task fits a tiny model. [nvBench](https://github.com/TsinghuaDatabaseGroup/nvBench).

NL4DV demonstrates the actual interaction in visualization interfaces. Its versions include semantic-parsing and LLM approaches; the current language-model mode requires an API key. [Project](https://nl4dv.github.io/nl4dv/), [showcase](https://nl4dv.github.io/nl4dv/showcase.html), [setup](https://nl4dv.github.io/nl4dv/documentation.html).

**Big risk:** binding words to unfamiliar columns. “Profit” cannot mean revenue minus costs unless that metric is explicitly supplied. An honest small library exposes ambiguous column choices. Evaluate the resulting grouped values and order, not just whether its JSON parses.

## 3. An animation input for visual editors

**Interaction:** Select three cards and type “fade in while moving up 20 pixels over half a second, stagger by 80 milliseconds.” The cards animate immediately and an editable timeline appears.

**Focused initial contract:** selected elements are supplied by the host editor. Recognize translation, opacity, scale, rotation, duration, delay, repeat, stagger, and sequential versus simultaneous composition. Start with one or two stages. Output validated timeline operations; ordinary browser code produces and plays keyframes.

**Why useful:** a reusable control for slide tools, page builders, interactive tutorials, and motion editors. Users can specify several coordinated controls in one sentence and then adjust the visible result.

**Concrete label generator:** sample valid timelines; render descriptions using authored temporal/parameter templates; retain operation identity, units, values, target order, and overlap relationships. Numerical timing is fully determined by the source timeline. Templates can express “while,” “together,” “then,” “after,” and “one after another” with explicitly defined meanings.

**Evidence level is weaker here:** Apple’s Keyframer demonstrates natural-language animation of named SVG elements using GPT-4 and CSS. It establishes a compelling interaction and an API-backed comparison, not an existing synthetic dataset or a tiny-model implementation. Our constrained timeline generator would have to be built. [Keyframer code and usage](https://github.com/apple-aiml-research/ml-keyframer).

**Big risk:** expressive language is not an exact label source. “Make it elegant” and “bounce naturally” do not identify unique timelines. Exclude such promises from an initial model. If the remaining interface feels like awkward English syntax for a handful of presets, reject it. This is the most visual candidate, but currently less substantiated than pattern search or chart control.

## Additional lead: spoken-style ordering becomes an editable configuration

“Two large pizzas, one with mushrooms and one with olives, no cheese on either” becomes two correctly configured items, with a live visual/cart preview. The difficult part is assigning modifiers and exclusions to the correct items, not extracting isolated food words.

The task has unusually good existing data evidence: Amazon publishes a food-ordering semantic-parsing dataset with synthetic menu/template generation and human-generated evaluation data. This supports a narrow one-menu experiment. Generalizing to arbitrary merchant catalogues is a separate problem; do not claim it follows automatically. [Food-ordering data and generation description](https://github.com/amazon-science/food-ordering-semantic-parsing-dataset), [PIZZA dataset](https://github.com/amazon-science/pizza-semantic-parsing-dataset).

This remains a secondary lead because merchant integration and domain specialization reduce its usefulness as a general frontend primitive.

## What the research changes

The best-supported directions in this pass are pattern search and bounded chart control. Animation has stronger immediate visual appeal but a larger gap between generated examples and language people naturally use. These are reasons to investigate, not a declaration that they beat gpu-lexer or gpu-time.

For every candidate, generate semantic objects first and derive labels from them. A program can verify whether execution matches the source object; it cannot certify that arbitrary generated prose means what its author intended. Independently authored real-input evaluation remains necessary.

No parameter budget should be promised yet. Short constrained outputs and explicit entity bindings make small-model experiments plausible; nested patterns, scope, and unseen schemas may demand more capacity than the reference taggers. On the M1 Pro/16 GB, begin with bounded datasets and models, measure memory/throughput, and let real-input accuracy determine whether a tiny browser artifact is credible.
