# Focused use cases with generated labels

> Earlier screening, superseded by [Interactive opportunities](interactive-opportunities.md). Word splitting, hard-wrap repair, and citations were rejected as insufficiently compelling; font recognition is outside the non-vision scope. Postal-address parsing is a lower bar, not the target. The proposals below are retained as research notes, not current recommendations.

## Selection constraints

An opportunity qualifies only if it has both:

1. A concrete way to generate labeled training pairs, or an existing bulk labeled corpus. Generating plausible inputs and asking an LLM to guess the answers does not satisfy this requirement by itself.
2. One small input/output task that can be demonstrated directly in the browser.

Frontend usefulness, an advantage over existing software, and M1 Pro/16 GB feasibility remain important. They are considered after the label source and focused contract are established.

The most promising pattern is to reverse a known operation: start with structured or correctly formatted material, render or corrupt it, and preserve the labels during that operation. Generated labels describe the source that produced an example; they do not prove that a lossy input has only one possible interpretation.

All generators below are proposals. No training runs, accuracy results, deployment sizes, or label-generation implementations have been produced.

## Shortlist

| Focused task | Exact source of labels | Browser demo | Main limitation |
| --- | --- | --- | --- |
| Restore missing word boundaries | Original spaces before concatenation | Type a hashtag/domain fragment; see word boundaries | Multiple segmentations can be valid |
| Repair hard-wrapped prose | Original paragraph boundaries and recorded wrap operations | Paste broken text; highlight joins and preserved paragraphs | Code, lists, and lost column order need protection |
| Parse one bibliographic reference | Fields retained by an annotated citation renderer | Paste a citation; color author/title/year/journal spans | Rendering can omit information; only recover visible fields |
| Identify a font from a text crop | Font file used to render each image | Drop a screenshot crop; see candidate fonts | Near-identical fonts and unseen fonts require ambiguity handling |
| Split one postal address into fields | Structured address fields before formatting | Paste address; color house/street/city/postcode | Begin with one country; parsing is not address verification |
| Parse a media filename | Metadata record used by the filename generator | Filename becomes title/year/season/episode chips | Existing parsers are strong; title numbers are ambiguous |

The strongest initial candidates are **word-boundary restoration** for a minimal labeling task, **hard-wrap repair** for editor utility, and **citation parsing** for an especially close analogue to gpu-lexer. **Font identification** is the clearest visual alternative with directly generated labels, but likely a larger experiment.

## 1. Restore missing word boundaries

### One-line use case

Turn `bestcoffeeshopinlondon` into `best coffee shop in london`.

### Generator

Take short, correctly spaced phrases from a suitable text corpus. Save each word boundary, remove the spaces, and optionally lowercase the result. The target is a binary boundary label after each character. Include intact single words as negative examples so the model does not split everything.

```text
Known phrase:  best coffee shop in london
Input:         bestcoffeeshopinlondon
Target:        best|coffee|shop|in|london
```

The corpus supplies real vocabulary and word combinations; annotation is automatic. Arbitrarily concatenating dictionary words can supplement training but should not replace natural phrases.

### Useful demo and applications

A live splitter for hashtags, lowercase identifiers, and domain-name fragments. A search index can use the recovered words to match queries; an interface can offer a readable label while preserving the original identifier.

### Why learning is relevant

Punctuation and casing may supply no boundaries. Dictionary-frequency segmentation is an established approach, exemplified by Wordninja.[^1] The experiment is whether a compact contextual classifier improves difficult splits or offers a useful size tradeoff.

### Evaluation boundary

Hold out source documents and phrase families before generating variants. Test proper nouns and vocabulary absent from training. An input such as `apart` can represent either one word or two; return candidates or uncertainty instead of claiming a unique reconstruction. Do not evaluate case restoration as part of the first task.

## 2. Repair hard-wrapped prose

### One-line use case

Recover paragraphs from text copied with a newline after every printed line.

### Generator

Start with correctly structured paragraphs and lists. Wrap lines at different widths. Optionally introduce a discretionary hyphen inside a word. Record exactly which newline was inserted by wrapping and which was an original structural boundary.

```text
Known text: The documentation explains the configuration.

Generated input:
The documentation explains the configu-
ration.

Target action at boundary: remove inserted hyphen and join
```

Targets are a small action set: keep boundary, replace newline with space, join without space, or remove a known wrapping hyphen and join. Preserve genuine lexical hyphens in both generation and expected output.

### Useful demo and applications

Two text panes with the edited boundaries highlighted. Integrate the operation into a rich-text editor, notes app, PDF clipping tool, or clipboard helper. It changes layout artifacts, not wording.

### Why learning is relevant

“Replace every newline with a space” destroys lists and paragraphs. Keeping every newline preserves the original problem. Dehyphenation packages already use language-model scoring to select possible joins, so there is a concrete existing approach to compare against.[^2]

### Evaluation boundary

Use real copied prose for the final test, with source documents excluded from training. Render through multiple wrapping/extraction paths so the model cannot merely recognize one generator. Protect code and table-like blocks. Lost multi-column reading order is outside scope. A paragraph break that leaves no observable trace may remain ambiguous.

## 3. Parse one bibliographic reference

### One-line use case

Paste a formatted citation and extract the author, title, year, venue, and other visible fields.

### Generator

Begin with a structured bibliographic record. Render it through several citation-style families while preserving the field provenance of each emitted span.

```text
Record:
author = A. Rao
year = 2024
title = Practical browser systems
venue = Journal of Web Tools

Rendered input:
Rao, A. (2024). Practical browser systems. Journal of Web Tools.

Labels:
AUTHOR       YEAR   TITLE                       VENUE
```

Start with a small annotated renderer that emits `(text, field)` pieces and concatenates them. This makes offsets exact. For wider style coverage, instrument a CSL processor to preserve provenance; plain formatted CSL output does not automatically provide token labels. Case changes, initials, abbreviations, punctuation, and omitted fields need explicit handling.

OpenAlex provides structured work metadata at scale, while the CSL project provides citation styles.[^3][^4] These are ingredients for a generator, not a ready-made aligned training set.

### Useful demo and applications

Color each field in the pasted citation and show an editable reference card or exportable record. Useful to reference managers, research editors, note apps, and bibliography importers.

### Why learning is relevant

Field order and punctuation vary substantially, while the output vocabulary is a small set of roles. AnyStyle provides an existing learned reference parser and training interface as a baseline.[^5]

### Evaluation boundary

Hold out complete works and citation-style families. Add copied line breaks and missing punctuation without silently inventing a unique answer. Extract only visible information: `et al.` does not expose omitted authors, and initials do not reveal full given names. No DOI lookup or bibliographic enrichment is included.

## 4. Identify a font from a cropped screenshot

### One-line use case

Given an image of a few words, return the most likely font families from a fixed supported catalogue.

### Generator

Select a font file, render random real words at varied sizes/weights, and save the font family as the label. Vary spacing, foreground/background, scale, antialiasing, and compression. All these variations retain the known font label.

Google Fonts makes font files available, and Storia's font-classification repository publishes training-data generation and training scripts, demonstrating this source of supervision.[^6][^7]

### Useful demo and applications

Drop a text crop; receive three candidate fonts with the same phrase rendered underneath for comparison. Useful in design tools, site builders, and typography utilities. The first version accepts a pre-cropped image and recognizes perhaps a few dozen chosen families; text detection and universal font recognition are separate tasks.

### Why learning is relevant

Pixels contain no font-name metadata. Robustness to different words, rendering environments, and image degradation requires generalization beyond exact image matching.

### Evaluation boundary

Hold out text strings and test screenshots from a rendering engine different from the generator. Include unsupported fonts. Some families share almost identical glyphs for a particular crop; a candidate list is appropriate. Synthetic labels are excellent, but visual domain transfer and a compact footprint remain experimental.

## 5. Split one postal address into components

### One-line use case

Parse one pasted address into house number, street, unit, city, region, and postal code.

### Generator

Start with structured address records. Render supported field orders, abbreviations, separators, line layouts, and omissions while recording field spans. Preserve real combinations for city/region/postcode; supplement with invented street/building names to discourage dictionary memorization.

libpostal documents training-data generation from open address/geographic data and formatting templates.[^8] This is an unusually direct precedent for the proposed supervision strategy.

### Useful demo and applications

A single text input whose address components are highlighted and transferred into editable fields. It is a focused extraction task, unlike filling arbitrary forms.

### Evaluation boundary

Choose one country initially. Hold out regions, streets, and formatter families; evaluate real pasted addresses. The output represents the text, not confirmation that the address exists or can receive mail. Compare with an existing parser under the same geographical scope.

## 6. Extract metadata from a media filename

### One-line use case

Turn `Example.Show.S02E03.1080p.WEB-DL.mkv` into title, season, episode, and resolution fields.

### Generator

Choose a title and metadata record, render filename conventions, and retain the spans used for each field. Vary separators, tag order, missing tags, and episode notations. Include titles containing numbers and words that resemble metadata.

### Useful demo and applications

A filename input with immediately updating metadata chips, or a bulk local-file organizer. Only information present in the filename is extracted; episode titles and external catalogue lookup remain separate.

### Evaluation boundary

Hold out titles and filename convention families. GuessIt and a JavaScript port already address this task, so a new implementation needs an accuracy, footprint, or maintainability advantage.[^9] It satisfies the generator/demo requirements but ranks below the other text ideas because its browser audience is narrower and its existing baselines are strong.

## Ideas that do not pass this filter yet

- **General semantic command search:** cheap paraphrase generation does not provide independent evidence of relevance across arbitrary apps. Larger teachers or annotated real queries would carry much of the work.
- **Arbitrary paste-to-form:** generating a contact block is easy; obtaining reliable labels for every business schema and inferred answer is not. The single-address task is a better bounded version.
- **Aesthetic crop selection:** a crop rectangle can be generated, but its aesthetic correctness cannot be inferred from generation alone. Human preferences or a teacher are needed. Document-corner detection has a much cleaner geometric label source.
- **Natural-language color descriptions:** the renderer knows a color, but it does not know which subjective phrase a person would use for it.
- **General cleanup by example:** synthetic programs provide labels, but the program that created an example is not necessarily the only program a person could intend. Useful, but a more complicated first problem.

## The initial experiment should validate the label source

For a selected task, generate a small, inspectable batch before training. Store the latent source, rendered input, target labels, and generator family. Check that labels remain aligned after every transformation. Explicitly record omitted information and ambiguous collisions.

Split source material and rendering families before augmentation. Keep a small independent real-input test set. A model that reproduces its own generator perfectly may still fail on actual pasted text, citations, addresses, or screenshots.

Text-boundary and token-role classifiers are realistic M1 Pro experiments. Font recognition needs a separate memory/throughput measurement and may produce a larger package. No specific training time or compressed size is established for any proposal.

## Sources

Checked September 14, 2026. These sources substantiate data paths and baselines; the proposed narrow browser implementations are not built.

[^1]: [Wordninja](https://github.com/keredson/wordninja): word-frequency-based segmentation and customizable vocabulary.
[^2]: [dehyphen](https://github.com/pd3f/dehyphen): language-model-based dehyphenation and paragraph joining.
[^3]: OpenAlex. [Work metadata](https://help.openalex.org/data/works/) and [API/data overview](https://help.openalex.org/api/).
[^4]: [Citation Style Language styles](https://github.com/citation-style-language/styles) and [citeproc command documentation](https://github.com/jgm/citeproc/blob/master/man/citeproc.1.md).
[^5]: [AnyStyle](https://github.com/inukshuk/anystyle): reference parsing and model training.
[^6]: [Google Fonts files](https://github.com/google/fonts).
[^7]: [Storia font-classify](https://github.com/Storia-AI/font-classify): synthetic dataset generation, training, and inference.
[^8]: [libpostal](https://github.com/openvenues/libpostal): address training data and formatting-based generation.
[^9]: [GuessIt](https://github.com/guessit-io/guessit) and [guessit-js](https://github.com/opensubtitles/guessit-js).
