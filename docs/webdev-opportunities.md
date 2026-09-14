# Tiny models that could become useful frontend dependencies

For the opportunity-led view—what a developer can add to an app and what friction it removes—start with [Product opportunities](opportunities.md). This document preserves the broader technical landscape and supporting comparisons.

## Recommendation

The strongest directions are **Scan** (document corners), **Sniff** (pasted-content recognition), **Crop** (responsive crop selection), and **Match** (semantic command matching). They expose small, reusable outputs that developers can combine with existing interfaces. They also offer concrete alternatives to a substantial dependency, a hosted inference step, or application-specific heuristics.

**Blocks**, a classifier over PDF text geometry, and **Map**, a column-to-schema matcher, are valuable second-tier opportunities for document and import tooling. Measure remains a reasonable learning exercise, but broader frontend utility puts it below these candidates.

This assessment separates three possible projects: training a new tiny model, distilling an existing model, and giving already-small weights a focused browser runtime. A good library can come from any of them. Creating a new neural architecture is not necessary for a useful result.

All proposed APIs, model budgets, rankings, and success criteria in this document are hypotheses. Existing-project claims are cited. No comparative browser benchmark, user-demand study, or M1 training run has been performed. Source capabilities were checked on September 14, 2026.

## The adoption test

A developer should be able to complete the sentence: “I install this because it lets my app ___ without ___.” Strong examples are “scan a page without loading OpenCV for corner detection” and “rank commands by meaning without sending each query to a server.”

The missing information must already be present locally. A model can find a crop in a selected image, label pasted text, or classify a supplied list of commands. It cannot obtain an unvisited page's metadata, verify a deliverable address, or discover current inventory without access to that information.

Approximation must also fit the interface. A suggested crop, ranked command, or editable import mapping tolerates uncertainty. Validating a phone number against current numbering rules or enforcing a token limit requires a different standard.

## Breadth of opportunities

“Replacement” below means the specific component described, not feature parity with an entire product. Rows marked exploratory have a plausible task but weaker evidence for a compact implementation or unsolved demand.

| Primitive | What developers could build | Potential burden removed | Initial assessment |
| --- | --- | --- | --- |
| **Scan**: four document corners | Camera scanner, receipt upload, whiteboard capture | OpenCV-based corner detection or a hosted detection step | Strong; clear boundary and training precedents |
| **Sniff**: pasted-content class | Smart paste, code playground, universal import preview | Loading many recognizers or asking an LLM what text is | Strong tiny-text candidate; compare existing detectors |
| **Crop**: crop rectangle/focal region | Avatar picker, CMS thumbnailer, responsive image editor | Hosted automatic crop selection | Strong visual utility; must beat smartcrop.js |
| **Match**: query-to-option score | Command palette, settings search, local action suggestions | Embedding/LLM requests for short candidate lists | High upside; semantic generalization is difficult |
| **Blocks**: PDF text-block labels | Local PDF cleanup, outlines, structured copy, chunking | Server layout classification for PDFs with text layers | Strong niche; preserve PDF.js and avoid OCR scope |
| **Map**: source-column/target-field score | CSV import assistant, spreadsheet migration | LLM-backed mapping suggestions | Strong utility; arbitrary schemas are a stretch |
| **Contact**: contact-information spans | Paste an email signature into a contact form | Broad NLP stack or extraction API | Useful; names, addresses, and locale ambiguity complicate labels |
| **Captions**: phrase and cue boundaries | Browser subtitle editor, caption reflow | Full language-model passes for segmentation | Good domain task; audio transcription remains separate |
| **Face boxes**: small face detector | Avatar framing, camera centering, assistive blur preview | General inference framework for one small detector | Strong packaging project; existing tiny models available |
| **Portrait mask** | Background effects, person-behind-text graphics | Hosted segmentation or broad runtime | Already competitive; runtime work more promising than retraining |
| **Read**: article-content blocks | Reader mode, local clipping, web text cleanup | Hosted extraction on already-loaded HTML | Useful but Readability is a strong existing baseline |
| **Reply**: email line roles | Collapse quoted history and signatures | Server-side mail cleanup | Good local-data benefit; representative labels are harder |
| **Paste table layout** | Recover an editable table from damaged plain text | Manual delimiter/layout selection | Distinctive but candidate generation may solve most cases |
| **Fields**: column semantic type | Better import controls and type suggestions | Broad inference stack or manual type assignment | Feasible; narrower than Map |
| **Measure**: quantity roles | Unit-aware form fields, shopping/spec imports | Complex grammar or extraction request | Feasible; weaker universal frontend need |
| **Keywords**: salient spans | Auto-suggest tags and search highlights | Full NLP pipeline or summarization request | Exploratory; compare cheap extractive methods first |
| **Token estimate**: approximate count | Live prompt-size meter | Exact tokenizer tables for a provisional display | Feasible learning task; approximation limits value |
| **Locale cues**: numeric/date style | Safer data import previews | Brittle per-column heuristics | Better as part of Fields than a separate package |
| **Caption punctuation** | Polish raw transcript text locally | Text-model API requests | Harder than cue breaks; many valid answers |
| **Upload quality**: blur/glare/cutoff flags | Retake suggestions before upload | Hosted image-quality classification | Useful if simple image statistics fail; exploratory |
| **Stroke intent**: drawn shape/gesture | Whiteboard gestures, diagram snapping | Custom gesture logic | Existing $1/$P recognizers set a very low complexity baseline |
| **Wake word / audio event** | Hands-free controls, sound-triggered interactions | Continuous speech-recognition requests | Viable category; audio runtime and false triggers add work |
| **Prefetch intent** | Earlier navigation preparation | Hand-tuned pointer heuristics | Site-specific data and existing tools weaken a universal model |
| **Password strength** | Compact password feedback | Dictionary-heavy estimator | Poor first replacement: believable scores are insufficient |
| **Language ID** | Localized editors, routing, spellcheck selection | Detection requests or large language tables | Useful but already crowded, including browser APIs |
| **General OCR, translation, alt text** | Rich upload and accessibility features | Hosted foundation-model calls | Valuable, but outside the forty-thousand-parameter class |

Sources grounding these categories include the detailed comparisons below, the [earlier parser-oriented ideas](project-ideas.md), and the alternative-library inventory near the end.

## 1. Scan: document corners as a browser primitive

### The developer-facing result

```text
detectPage(image) → four normalized corners + confidence
```

A developer draws an adjustable quadrilateral over a camera frame. Once accepted, conventional geometry rectifies the page into a flat image. Useful hosts include expense tools, school submission portals, document upload forms, note apps, and whiteboard capture.

This is a particularly clean learned component: return eight coordinates and confidence. Do not combine it with OCR, document understanding, authenticity checks, or curved-page unwarping in version one.

### Existing burden and credible alternative

jscanify implements browser document scanning using OpenCV.js. It gives a concrete baseline for detection plus extraction, rather than requiring an invented competing architecture.[^1]

MakeACopy publishes a DocQuadNet training pipeline using a MobileNetV3 backbone, a feature pyramid, a mask head, and four corner heatmaps. It describes UVDoc pretraining, SmartDoc fine-tuning, background augmentation, and sequence-disjoint evaluation. That is evidence for a practical training path, not proof its model can already meet a tiny browser budget.[^2]

### A plausible build

Begin with a small convolutional model over a reduced-resolution image. Predict corner heatmaps and a document-presence score; derive corner coordinates in deterministic postprocessing. A mask is an optional training aid if it demonstrably improves corners.

Generate additional examples by rendering document-like rectangles under perspective, lighting, and background variation. Mix real labeled photos early: a white quadrilateral on random backgrounds alone teaches an oversimplified task. Hold out documents, capture sequences, and backgrounds together where appropriate.

A target of at most roughly 2 MB for the complete optional detection module is a provisional product constraint, not a measured result. Low-resolution training or adapting a compact backbone is plausible on the M1 with small batches. The reference training stack may require changes; native MPS compatibility has not been established for that repository.

### What would make it worth shipping

Compare against OpenCV contour detection and a smaller purpose-built edge/quad detector. Measure corner error, retained page area, false document detections, manual correction rate, cold download, and frame latency. Test receipts, dark paper, clutter, low contrast, and partially visible pages.

The claim should be “a smaller corner detector for this scan workflow.” OpenCV is not needed for the final product if a small perspective-warp implementation suffices, but all replacement geometry must be counted in the footprint. Loading OpenCV solely to perform the warp would undermine much of the size argument.

**Why it ranks highly:** tangible dependency substitution, a visual result people understand instantly, and a sufficiently narrow output to evaluate rigorously.

## 2. Sniff: recognize what was pasted

### The developer-facing result

```text
classifyText(text) → ranked kinds + confidence + optional dialect hints
```

An editor can offer “Paste as table,” a playground can choose a code pane, and a support form can offer a stack-trace viewer. Initial classes might cover JSON, CSV/TSV, SQL, source code, diff, stack trace, Markdown, prose, and unknown. A first version classifies the whole snippet; mixed-document segmentation is a separate extension.

This is broader than repairing pasted tables. It is a routing primitive that can improve many editors without owning their parsing or rendering.

### Existing burden and credible alternative

The file-type library primarily identifies binary formats through signatures and explicitly distinguishes its scope from general text-format detection. Magika is a learned content-type detector and already has a JavaScript package, making it a direct benchmark rather than an ignored competitor.[^3][^4]

The opportunity is a particularly small detector tuned to short, incomplete clipboard text and UI decisions. General file classification and short-snippet classification have overlapping but different input distributions. This distinction must show up in a benchmark to justify another detector.

### A plausible build

Train on short excerpts from source-disjoint repositories, generated structured data, error fixtures, and prose. Labels can come from known origins, generation, and parser checks. Include truncation, missing delimiters, copied prompts, and genuinely ambiguous snippets.

A hashed character/word-feature classifier or small convolutional sequence model is an appropriate first candidate. Feature hashes, punctuation distributions, line shape, and local transitions should supply substantial signal. Compare this with a linear classifier before adding a more elaborate network.

Strict full-input parsers can handle obvious JSON or valid delimited data directly. The learned model handles ambiguous/incomplete cases and ranks likely interpretations. It should not claim that successful classification validates syntax or authorizes execution.

### What would make it worth shipping

A complete module target below 250 KB is worth testing. Measure top-one/top-three classification, reliable unknown rejection, CPU latency, and transfer size against Magika, grammar-based detection, and a tiny linear classifier. Very short strings such as `true` may deserve ambiguity rather than a forced class.

Hold out projects and snippet origins. An evaluation consisting of random excerpts from the training repositories will overstate generalization.

**Why it ranks highly:** closest to the compact gpu-lexer theme, easiest local-training path in the new shortlist, and useful to multiple kinds of web editor. The benefit depends on supporting actual paste decisions better or more compactly than existing alternatives.

## 3. Crop: useful rectangles for responsive images

### The developer-facing result

```text
suggestCrop(image, aspectRatio) → crop rectangle + alternate candidates
```

One image can receive suggested crops for an avatar, product card, banner, and story. A CMS can preview them before upload. An image editor can offer a sensible starting rectangle while leaving the final decision visible and reversible.

### Existing burden and credible alternative

Cloudinary's automatic gravity selects visually important regions for requested crops. A local crop selector could avoid that analysis request when the source image is already in the browser; it would not replace image hosting, encoding, or CDN delivery.[^5]

smartcrop.js already does local crop selection using image features such as edges, skin-like color, and saturation. Its deliberately simple implementation is the relevant lightweight baseline. A neural package must improve crop preference or consistency enough to justify extra bytes.[^6]

Grid-anchor image-cropping research supplies datasets, pretrained models, and training code. The referenced implementation uses an older Python/PyTorch stack, so its methodological value is clearer than its readiness to run unchanged on an M1.[^7]

### A plausible build

Use a compact image encoder once, then score a deterministic set of crop candidates for the requested aspect ratio. This avoids rerunning a full encoder for every crop. Training can use human crop preferences, an existing crop model as a teacher, and independently evaluated user preferences.

Begin with one domain such as product thumbnails or portraits. Retaining a subject and making an aesthetically good crop are different targets; face detection alone cannot decide all compositions. Treat a compact pretrained vision backbone as the starting point before attempting from-scratch semantic vision training.

### What would make it worth shipping

Compare center crop, smartcrop.js, and the learned suggestion in a blinded preference test on source-disjoint images. Measure catastrophic subject cuts separately from average preference. Test multiple aspect ratios and sensitivity to small ratio changes.

A provisional complete optional-module budget of 1–3 MB is more honest than assuming a 40 KB network can learn broad image composition. A face-only crop component may be much smaller, with a correspondingly narrower claim.

**Why it ranks highly:** a widely reusable visual interaction with an identifiable hosted counterpart. Its main risk is producing only a marginal gain over a cheap local baseline.

## 4. Match: semantic ranking for commands and options

### The developer-facing result

```text
rankOptions("make the writing bigger", commands)
  → "Increase font size", "Zoom in", ...
```

Commands are supplied by the application, including names and short descriptions. This could power settings search, command palettes, documentation navigation, and small offline catalogues. The model ranks options; the application still owns execution and permissions.

### Existing burden and credible alternative

Fuse.js provides lightweight lexical fuzzy matching. Model2Vec provides a stronger semantic baseline through static embeddings and documents CPU distillation from sentence-transformer teachers. It already addresses some of the size/speed problem, so a new library must be compared with it.[^8][^9]

The possible network saving is specific: local query-to-candidate scoring can avoid sending each query to an embedding or language-model service. It does not remove requests required to retrieve remote catalogue entries or execute selected commands.

### A plausible build

Encode candidate descriptions once. Use a small encoder and pairwise scorer, or static embeddings plus a lightweight learned ranking head. Training pairs associate paraphrases with the correct command and with confusing negatives. Include negation, related actions, and “none of these.”

The critical distinction is **new wording for known commands** versus **new commands from a different app**. A fixed intent classifier solves only the first. A reusable package requires candidate-conditioned scoring and evaluation on applications and intents excluded from training.

CLINC150 is a useful intent/out-of-scope benchmark, while Google's Schema-Guided Dialogue dataset includes natural-language service schemas and supports studying generalization. Neither directly proves quality for frontend command palettes; a command-specific evaluation set is still required.[^10][^11]

### What would make it worth shipping

Measure recall at three, ranking quality, and incorrect confident matches to unrelated queries. Compare Fuse plus thoughtfully supplied aliases, simple word overlap, Model2Vec, and a compact sentence encoder. Prevent synonyms or teacher-generated paraphrases of held-out commands from leaking into training.

A 1–5 MB exploration budget for a semantically useful package is plausible as a target, not a demonstrated result. A universal matcher in tens of kilobytes is a much stronger and currently unsupported claim. Adapting a compact pretrained/static model is more credible on the M1 than learning broad semantics from scratch.

**Why it ranks highly:** widest potential developer surface and repeated-request savings. **Why it is riskier:** an attractive demo on a fixed command list can conceal weak cross-application transfer.

## 5. Blocks: structure already-extracted PDF text

### The developer-facing result

```text
classifyBlocks(textItemsWithPositions) → heading/body/header/footer/caption/other
```

A PDF viewer can offer cleaner copying, section outlines, or better chunks for local search. The input is an existing text layer with coordinates and style information. The model identifies structure; the original characters remain intact.

This can replace a server layout-classification stage for a bounded class of digitally generated PDFs. PDF.js or another PDF parser remains a dependency. Scanned PDFs need OCR, and tables need additional structure inference, so “local PDF-to-Markdown replacement” would overstate version one.

### Data and model

DocLayNet contains 80,863 annotated pages with 11 layout classes and offers auxiliary PDF text cells with coordinates. Those assets support mapping textual cells into annotated regions after reconciling their coordinate systems.[^12]

Train a small classifier or contextual sequence model on normalized geometry, relative font size, text length/shape, repetition across pages, and neighboring blocks. Begin with block roles; reading-order edges and hierarchy are separate prediction targets requiring suitable labels. DocLayNet's region labels alone do not supply a complete reading-order graph.

### What would make it worth shipping

Compare geometric/font heuristics and repeated-header detection with learned labeling. Hold out whole documents, publishers, and templates. Measure missing body text, spurious headers, correct section boundaries, and copy quality in real viewers.

Feature-based training is plausible on the M1. Start with a dataset subset rather than loading all page imagery; the text-geometry approach intentionally avoids a large visual encoder. A sub-megabyte add-on is a hypothesis to test, not a guarantee.

**Why it is interesting:** a substantial part of document understanding can use text and geometry already present in the browser, with no need to regenerate the text.

## 6. Map: local column-to-schema matching

### The developer-facing result

```text
suggestMapping(sourceColumns, targetFields)
  → "contact_mail" ↦ "email", "organisation" ↦ "company", ...
```

Target fields include descriptions and expected types; source columns include headers and sample values. The result is a proposed mapping plus unmatched/ambiguous columns. This is more immediately useful in import wizards than generic column labels alone.

### Data and model

Combine deterministic validators, semantic-type features, and a learned source/target pair score. An ordinary assignment algorithm can enforce one-to-one mappings where the application requires them. Treat a target field's identifier as arbitrary: its supplied description, type, and examples need to carry meaning.

Sherlock establishes semantic column typing as a learned task and supplies code/data, but it does not by itself solve arbitrary schema matching. Mapping supervision can come from generated schemas, real manually mapped imports, and reviewed paraphrases.[^13]

### What would make it worth shipping

Evaluate on target schemas, source organisations, and tables held out from training. Include multiple emails, billing versus shipping fields, identifiers resembling numbers, empty columns, and schemas with no suitable destination.

Measure the number of human corrections needed, not just pairwise classification accuracy. Compare header normalization, aliases, validators, and assignment before adding semantics. A model can remove a hosted mapping request, but it does not replace validation, deduplication, or the import backend.

**Why it is interesting:** it improves a repeated, recognisable frontend workflow. **Why it is harder than Fields:** genuinely new field meanings demand semantic generalization; a fixed catalogue can be much smaller.

## The overlooked option: reuse a tiny model, remove its broad runtime

face-api.js documents a quantized tiny face detector of about 190 KB, while its API uses TensorFlow.js. MediaPipe supplies person/background segmenters and a web integration. These are evidence that useful vision weights can already be compact.[^14][^15]

A standalone face-box or portrait-mask package could expose an ImageBitmap/VideoFrame-oriented API, implement only the selected model's operations, and return boxes or a mask texture. Existing weights could establish correctness before considering retraining. This is model-runtime engineering with a concrete target, not a reason to create a general inference framework.

It is necessary to measure the actual selected framework build and transitive assets first. Package-manager unpacked size is not transfer size, and tree shaking or an existing WebGPU runtime may already remove much of the presumed overhead. A 190 KB weight file does not imply a 190 KB complete package.

GPU-resident mask output can be particularly useful for canvas effects, because the renderer can consume the mask without a CPU round trip. Still-image detection may work well on CPU. Device initialization, supported operators, precision parity, camera preprocessing, and frame scheduling are material implementation work.

This route has a stronger chance of quickly demonstrating utility than training general segmentation from scratch. Its novelty would be the focused integration, runtime footprint, and performance evidence.

## Smaller bets worth retaining

**Captions.** Predict good word boundaries for subtitle lines/cues, then use a deterministic optimizer for duration, width, and reading-speed constraints. An ACL paper studies subtitle segmentation using masked-language-model scores, and MuST-Cinema addresses missing subtitle-break annotations in other corpora.[^16] A tiny student could learn those decisions; ASR and translation remain separate. Evaluate perceived reading quality as well as reference-break agreement because multiple valid layouts exist.

**Contact paste.** Extract name, organisation, job title, email, and phone spans from a signature or short contact block. This is useful in address books and lead forms. A broader NLP package is a real alternative: winkNLP documents browser models with gzipped sizes starting around 890 KB.[^17] A narrow model would need a demonstrably smaller complete footprint or better task results; splitting human names or inferring address semantics must remain optional.

**Approximate token meter.** Train a small count regressor from exact tokenizer labels, using byte patterns and script statistics. This could improve on character-count heuristics for a live provisional meter without shipping every merge table. Exact browser tokenizers already exist, including gpt-tokenizer and ai-tokenizer.[^18] A count predictor is unsuitable for exact limits, token IDs, or billing reconciliation. Benchmark tail underestimation on code, multilingual text, and unusual byte sequences before treating it as useful.

**Upload preflight.** A small classifier could flag cutoff pages, strong glare, or likely unusable captures before submission. Start with a specific acquisition workflow; blur metrics and brightness/clipping statistics are inexpensive baselines. This is an exploratory product extension to Scan, with dataset quality and acceptable rejection rates still unestablished.

## Why some apparent opportunities fall down

| Tempting replacement | What the evidence changes |
| --- | --- |
| Phone-number library | libphonenumber-js already offers metadata tradeoffs. A predictor cannot replace current numbering-plan rules for authoritative validation.[^19] |
| Password-strength library | zxcvbn incorporates guessability patterns and dictionaries. Training a small student to imitate its score does not establish reliable strength estimates.[^20] |
| Ordinary sentence splitting | Intl.Segmenter already exposes locale-sensitive sentence/word/grapheme segmentation. A model needs a harder niche such as punctuation-free transcripts.[^21] |
| Balanced heading wrapping | CSS text-wrap provides native balance/pretty behavior. Add a model only for a distinct semantic-layout task that native layout does not solve.[^22] |
| Simple drawn shapes | $1/$P recognizers offer compact, train-by-example gesture recognition without neural training infrastructure.[^23] |
| Language detection | Existing small libraries and browser language-detection APIs reduce differentiation. Browser support and model downloads still need checking per target.[^24] |
| Background removal | Browser implementations already exist. A portrait-only tiny model is not equivalent to arbitrary product/object cutouts.[^15][^25] |
| Navigation prediction | ForesightJS and Guess.js already address predictive prefetching. A universal neural alternative needs real behavior data and a win over simple timing rules.[^26] |
| Remote link preview | If page data is absent locally, an inference model cannot eliminate the retrieval step while retaining trustworthy metadata. |
| General OCR or translation | These need substantially broader learned capability than token/region classification. A limited camera or text primitive is a more credible first project. |

## How to compare “cheaper” honestly

For each selected task, measure the same workload and supported scope on both implementations. Count code, weights, vocabulary, WASM, shaders, and preprocessing assets. Report raw, gzip/Brotli, cold-start, warm single-input, batch, peak memory, and output-quality measurements separately.

A network alternative has different economics depending on use. Local inference pays an initial download and device compute; hosted inference pays request latency, service work, and usually ongoing cost. If a local model is downloaded once and used repeatedly, the comparison improves with reuse. If a widget is used once on a slow phone, the model download can dominate. Do not infer a universal financial break-even point without actual request pricing, cache behavior, and task frequency.

Also compare against removing the need for runtime inference: precompute crops at upload, classify static content at build time, use declared clipboard MIME data, or allow a user to select a type. A model is strongest for fresh, ambiguous, user-provided inputs that need an immediate result.

## Research priorities

| Priority | Candidate | First decisive experiment |
| --- | --- | --- |
| 1 | **Scan** | Compare a compact corner model with contour/quad baselines on independent phone captures; measure complete browser assets |
| 2 | **Sniff** | Build a source-disjoint short-snippet benchmark and compare linear features, Magika, and a tiny neural classifier |
| 3 | **Crop** | Test blinded crop preference against center crop and smartcrop.js across requested aspect ratios |
| 4 | **Match** | Test unseen applications and command sets against Fuse with aliases and Model2Vec |
| 5 | **Blocks** | Compare text-geometry labeling with font/position heuristics on publisher-disjoint PDFs |
| 6 | **Map** | Measure corrections per import on unseen schemas against aliases, validators, and deterministic assignment |

Choose **Scan** for the clearest useful dependency replacement, **Sniff** for the closest very-small-text-model project, **Crop** for a polished visual demo, or **Match** for the most ambitious broadly reusable API. The M1 Pro is a reasonable machine for initial experiments in all four, with pretrained adaptation more credible than broad from-scratch training for Crop and Match. None requires buying hardware before measuring a small run.

## Sources

[^1]: Puffinsoft. [jscanify repository and OpenCV.js integration](https://github.com/puffinsoft/jscanify).
[^2]: MakeACopy. [DocQuadNet-256 training guide](https://github.com/egdels/makeacopy/blob/main/training/README.md).
[^3]: Sindre Sorhus. [file-type scope and implementation](https://github.com/sindresorhus/file-type).
[^4]: Google. [Magika JavaScript package](https://github.com/google/magika/blob/main/js/README.md). Fratantonio et al. [Magika paper](https://arxiv.org/html/2409.13768v1), 2024.
[^5]: Cloudinary. [Automatic gravity for image crops](https://cloudinary.com/documentation/image_automatic_gravity), documentation updated June 19, 2026.
[^6]: Jonas Wagner. [smartcrop.js](https://github.com/jwagner/smartcrop.js).
[^7]: Hui Zeng et al. [Grid Anchor based Image Cropping: code, datasets, and models](https://github.com/HuiZeng/Grid-Anchor-based-Image-Cropping-Pytorch), CVPR 2019 / TPAMI 2020 work.
[^8]: Fuse.js. [Fuzzy-search library](https://www.fusejs.io/).
[^9]: Minish Lab. [Model2Vec repository](https://github.com/MinishLab/model2vec) and [distillation documentation](https://minish.ai/packages/model2vec/distillation/).
[^10]: Larson et al. [Intent Classification and Out-of-Scope Prediction dataset](https://github.com/clinc/oos-eval), EMNLP 2019.
[^11]: Google Research. [Schema-Guided Dialogue dataset](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue).
[^12]: Pfitzmann et al. [DocLayNet dataset, annotations, and auxiliary PDF text cells](https://github.com/DS4SD/DocLayNet), 2022.
[^13]: Hulsebos et al. [Sherlock semantic type detection](https://github.com/mitmedialab/sherlock-project), 2019.
[^14]: Vincent Mühler. [face-api.js and the 190 KB quantized tiny face detector](https://github.com/justadudewhohacks/face-api.js).
[^15]: Google. [MediaPipe Image Segmenter guide](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter), updated August 17, 2026.
[^16]: [Unsupervised Subtitle Segmentation with Masked Language Models](https://aclanthology.org/2023.acl-short.67/), ACL 2023. [MuST-Cinema: a Speech-to-Subtitles corpus](https://arxiv.org/abs/2002.10829), 2020.
[^17]: Wink. [winkNLP language models](https://winkjs.org/wink-nlp/language-models.html).
[^18]: Niieani. [gpt-tokenizer](https://github.com/niieani/gpt-tokenizer). Coder. [ai-tokenizer](https://github.com/coder/ai-tokenizer).
[^19]: Catamphetamine. [libphonenumber-js metadata options](https://github.com/catamphetamine/libphonenumber-js/blob/master/README.md).
[^20]: Dropbox. [zxcvbn](https://github.com/dropbox/zxcvbn).
[^21]: MDN. [Intl.Segmenter](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter).
[^22]: MDN. [CSS text-wrap](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/text-wrap). WebKit. [Better typography with text-wrap: pretty](https://webkit.org/blog/16547/better-typography-with-text-wrap-pretty/), 2025.
[^23]: University of Washington. [$1 and related gesture recognizers](https://depts.washington.edu/acelab/proj/dollar/index.html).
[^24]: Chrome for Developers. [Language detection with built-in AI](https://developer.chrome.com/docs/ai/language-detection). See [full research](research.md) for CLD3, fastText, and Desert Ant comparisons where covered.
[^25]: IMG.LY. [Background removal in the browser](https://github.com/imgly/background-removal-js).
[^26]: [ForesightJS](https://github.com/spaansba/ForesightJS) and [Guess.js](https://github.com/guess-js/guess).
