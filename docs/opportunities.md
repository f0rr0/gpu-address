# Product opportunities for small local intelligence

## What is being selected

The goal is a useful capability a web developer could add to an application. A small model is one possible implementation of its difficult decision. The opportunity should be understandable before discussing models, architectures, or inference frameworks.

The strongest candidates are **paste-to-form**, **example-driven bulk cleanup**, **meaning-aware command search**, and **repairing pasted text**. They combine familiar user friction with a compact result that a frontend can preview and use immediately. This ranking is an analytical judgment; it is not a market-size estimate or a finding that competing products do not exist.

## 1. Paste one block of text into an entire form

**Experience.** Copy a contact block from an email, press Paste into form, and preview the populated name, company, email, phone, and address fields. Change anything uncertain before accepting. The same integration could serve contact creation, registration, vendor onboarding, and delivery details.

**Why a developer would install it.** It replaces repetitive field-by-field copying. It could also remove a server inference round trip for ordinary extraction tasks.

**Concrete evidence.** Syncfusion's Smart Paste Button detects form fields and accepts descriptions derived from labels or supplied attributes. Its API documents a server callback for obtaining the AI response. Telerik also offers an AI-powered SmartPasteButton. The interaction is an established product capability, not merely an imagined model demo.[^1][^2]

**The opportunity.** A small framework-independent local extraction library for common field types. It returns values copied from source spans and proposed field assignments. Start with contact/company blocks; arbitrary business reasoning, rewritten answers, and inferred checkbox values are a much broader feature set than the small local version promises.

**Why learning might help.** Recognizing names, organisations, titles, and address components depends on context and arrangement; email and phone regexes solve only part of the task. Ambiguous fields can remain empty.

**First test.** Compare corrections and completion time against manual paste plus regex extraction on real, independently labeled contact blocks. The decisive result is fewer corrections with a small complete download.

## 2. Fix one row, apply the same cleanup to the rest

**Experience.** In a data grid, change `INV_2026_0042.pdf` to `0042`, or `Jain, Sid` to `Sid Jain`. Give another example if necessary. The grid previews the corresponding transformation across the remaining rows.

**Who could use it.** CSV importers, spreadsheet components, file managers, admin tools, and bulk product editors. It exposes a useful automation capability without making the user write regexes, formulas, or a natural-language prompt.

**The opportunity.** A local “transform by example” primitive, similar in interaction to Flash Fill. It should support a deliberately bounded set of operations: extracting substrings, splitting, joining, casing, replacing separators, and limited conditional formats.

**Why a small model might help.** Many candidate transformations can fit two examples. A learned scorer could prefer plausible transformations or guide the search. Ordinary code can verify candidates against all supplied examples and apply the selected transformation deterministically.

**Evidence and limit.** Microsoft documents both example-driven string transformation and neural-guided search. The latter provides a precedent for learning the search preference, rather than asking a model to generate every output row.[^3] A learned scorer is useful only if it improves over simple synthesis/ranking rules. Matching examples is not proof of the user's intent on unseen rows, so the preview is essential.

**First test.** Measure examples required, search time, and preview corrections across held-out transformation families. This is the most distinctive data-tool opportunity in the list.

## 3. A command palette that understands what the user wants

**Experience.** “Make the writing bigger” finds Increase font size. “Stop getting these emails” finds Notification preferences. “Where are my invoices?” finds Billing history.

**Who could use it.** SaaS dashboards, editors, settings panels, component documentation, and applications with many actions that users cannot remember by name.

**The opportunity.** Developers supply command names and descriptions. The library ranks those supplied options locally, as a more meaning-aware alternative to lexical fuzzy matching or a hosted semantic-ranking request.

**Why learning might help.** The user's words often share no characters with the command's label. Typo tolerance alone does not bridge that gap. However, sensible aliases are an inexpensive baseline and may be sufficient for a small app.

**First test.** Try completely unseen applications and command lists. A system that recognizes paraphrases of one fixed catalogue is a narrower product. Rank suggestions rather than executing inferred actions. The likely useful implementation may be larger than gpu-time; extreme smallness should not be assumed.

Existing alternatives and evaluation leads are in the [technical opportunity assessment](webdev-opportunities.md#4-match-semantic-ranking-for-commands-and-options).

## 4. Paste from a PDF without spending five minutes repairing it

**Experience.** Copy a paragraph from a PDF into an editor. The editor joins artificial line breaks, fixes words broken across lines, and retains real paragraphs and lists. It previews changes and leaves code, tables, and uncertain cases alone.

**Who could use it.** Rich-text editors, note apps, email composers, knowledge bases, annotation tools, and browser extensions.

**The opportunity.** A narrowly scoped paste-cleanup library that preserves wording. It could replace brittle “remove all newlines” rules or sending the text to an LLM to clean up formatting. Existing PDF extraction tools explicitly include paragraph reconstruction and dehyphenation, confirming these are separate tasks that can be isolated.[^4]

**Why it fits a tiny prediction task.** At each line boundary, choose join, retain, or dehyphenate-and-join. A separate classification can protect code and table-like regions. Those few decisions can improve a large amount of text without generating new prose.

**Training opportunity.** Start with correctly structured documents and render different wrapping widths and hyphenation patterns; the original structure supplies labels. Independently evaluate real copied text, especially headings, poetry, lists, and intentional hyphens. Multiple-column text with lost reading order needs a separate solution.

**First test.** Compare exact reconstructed text and harmful merges against straightforward heuristics. This is the strongest small, focused first experiment in the opportunity-led shortlist.

## 5. CSV import without the repetitive mapping screen

**Experience.** Upload a CSV. The import UI suggests `contact_mail → email` and `organisation → company`, preserves leading zeros in identifiers, and asks only about ambiguous columns.

**Who could use it.** CRMs, inventory tools, mailing-list tools, finance dashboards, and reusable data-grid/import components.

**The opportunity.** Local mapping suggestions from headers, sample values, and the destination schema. Avoid an inference request when these are the only inputs needed for the decision.

**The difficult judgment.** Headers are inconsistent and several columns may appear equally plausible. Typing a column and understanding a business-specific destination field are different tasks. Start with common field families and meaningful schema descriptions.

**First test.** Count mapping corrections per import on previously unseen schemas. Compare against normalized names, aliases, and validators. The [technical notes](webdev-opportunities.md#6-map-local-column-to-schema-matching) cover the distinction between a reusable matcher and a fixed set of type labels.

## 6. Select the phrase you meant, not just the word you clicked

**Experience.** Selecting part of a company name can offer the whole name. Clicking within a measurement can select the complete amount and unit. A reading tool can select a complete phrase before highlighting, searching, linking, or annotating it.

**Who could use it.** Document readers, mobile editors, annotation tools, research applications, and rich-text components.

**The opportunity.** Given text and a user-indicated position, suggest a few meaningful spans. This would extend the browser's ordinary word-level selection without requiring a general NLP pipeline or a request per interaction.

**Why learning might help.** The appropriate span depends on nearby words and the selection task. Microsoft Research defines smart selection as predicting the span a user intended after touching one word, so there is direct research precedent.[^5]

**First test.** Measure selection adjustments for a few useful span families. Preserve native selection behavior and offer expansion explicitly until usefulness is established. Predicting one universally correct phrase would be the wrong contract: users can intend different spans.

## 7. Images that crop sensibly wherever a component places them

**Experience.** One uploaded image gets sensible suggested crops for a card, banner, square thumbnail, and avatar. The focal subject stays visible as the aspect ratio changes.

**Who could use it.** CMSs, ecommerce tools, site builders, publishing tools, and image components.

**The opportunity.** Local crop suggestions before upload, with an optional manual focal-point override. This can avoid a hosted crop-analysis step and make responsive preview immediate. Cloudinary already offers automatic gravity; smartcrop.js is a local baseline.[^6]

**First test.** Blinded preference and subject-cutoff comparisons against center crop and the existing local algorithm. A model has to improve the result enough to justify its download. Suggestions about safe text placement on an image are a possible later extension, not part of the initial crop contract.

## 8. Add a camera scanner without adopting a broad vision stack

**Experience.** A mobile web upload field finds the page, lets the user correct its corners, and straightens it before submission.

**Who could use it.** Expense forms, school portals, note apps, insurance workflows, and document upload components.

**The opportunity.** A focused page-boundary detector plus ordinary perspective correction. jscanify's use of OpenCV provides a concrete dependency baseline.[^7] The savings would concern this task, not replacing all of OpenCV or adding OCR.

**First test.** Complete module download, detection quality, and manual corrections on varied phone captures. This is the strongest visual opportunity with a clear dependency-replacement story, although training and integration are more work than text-boundary cleanup.

## 9. Captions that break where a person would pause

**Experience.** Given words and timestamps, a browser editor produces readable caption chunks rather than cutting mid-phrase or leaving one dangling word.

**Who could use it.** Video editors, screen recorders, course tools, and caption styling components.

**The opportunity.** Local phrase-boundary suggestions combined with deterministic width, duration, and reading-speed constraints. Speech recognition and translation remain separate.

**First test.** Compare reader preference and correction effort against fixed-length and punctuation-based splitting. Research distinguishes subtitle boundary prediction from ordinary line-length constraints.[^8] A small decision model is plausible; no particular model size or quality has yet been established.

## 10. Pasted logs become a useful error card

**Experience.** A user pastes a build failure or stack trace into a support form. The UI highlights the error message, extracts likely file/line references, and collapses repetitive dependency frames.

**Who could use it.** Developer support tools, issue forms, browser IDEs, playgrounds, and CI dashboards.

**The opportunity.** Recognize roles in unstructured diagnostic text and return original spans. This is assistive presentation, not root-cause analysis or an AI-generated fix.

**Why it is worth exploring.** It is directly relevant to developers and has an obvious demo. Known framework fixtures and generated failing programs could supply examples. However, the evidence for an unmet need beyond small stack-trace parsers is weaker than for the leading opportunities.

**First test.** Hold out runtimes/frameworks and compare with conventional parsers. If structured errors are already available, use those directly.

## Choosing among them

| Priority being optimized | Opportunity |
| --- | --- |
| Clearest existing server-AI feature to make local | Paste-to-form |
| Most distinctive capability for data tools | Fix one row, apply the pattern |
| Smallest, clearest learned decision to investigate | Repair pasted text boundaries |
| Broad frontend reuse with higher technical risk | Meaning-aware command search |
| Strongest visual dependency-replacement demo | Camera page detection |
| Publishing/image component utility | Responsive crop suggestions |

The immediate recommendation is to evaluate **paste-to-form** and **paste cleanup** side by side: the former has a clearer existing AI-service counterpart, while the latter is a tighter fit for an extremely small model. Keep **example-driven bulk cleanup** as the more ambitious idea with a distinctive interaction.

Before selecting implementation, collect real examples of the chosen friction and establish what a competent non-ML baseline can do. The opportunity is strongest when a small learned decision unlocks a useful interaction that otherwise takes manual work, a substantial dependency, or a remote inference request.

## Sources

Primary sources checked September 14, 2026. Existing product capabilities substantiate possible use cases; they do not establish demand for a new package or its achievable performance.

[^1]: Syncfusion. [JavaScript Smart Paste Button](https://www.syncfusion.com/javascript-ui-controls/js-smart-paste-button) and [server AI callback API](https://ej2.syncfusion.com/react/documentation/api/smart-paste-button/smartpastebuttonmodel).
[^2]: Telerik. [SmartPasteButton overview](https://www.telerik.com/products/aspnet-ajax/documentation/controls/smartpastebutton/overview).
[^3]: Microsoft Research. [Neural-Guided Deductive Search](https://www.microsoft.com/en-us/research/blog/neural-guided-deductive-search-best-worlds-approach-program-synthesis/), April 27, 2018. Microsoft Support. [Using Flash Fill in Excel](https://support.microsoft.com/en-us/excel/using-flash-fill-in-excel).
[^4]: PDF2Text authors. [Layout-aware extraction pipeline, paragraph reconstruction, and line joining](https://github.com/CD11b/pdf2text). This is a technical precedent, not a browser-package size comparison.
[^5]: Microsoft Research. [Smart Selection](https://www.microsoft.com/en-us/research/publication/smart-selection/).
[^6]: Cloudinary. [Automatic crop gravity](https://cloudinary.com/documentation/image_automatic_gravity). Jonas Wagner. [smartcrop.js](https://github.com/jwagner/smartcrop.js).
[^7]: Puffinsoft. [jscanify](https://github.com/puffinsoft/jscanify).
[^8]: [Unsupervised Subtitle Segmentation with Masked Language Models](https://aclanthology.org/2023.acl-short.67/), ACL 2023.
