# Building tiny models for the browser

**An M1 Pro with 16 GB of unified memory is enough to build useful models in this category.** It is a particularly good fit for small token taggers, language detectors, classifiers using pretrained embeddings, and modest fine-tuning experiments. It is less suited to reproducing the enormous datasets and repeated training runs behind some production models. The main constraint is usually the data and evaluation pipeline, followed by training throughput—not whether a model can fit into memory at inference time.

The two recent examples are **Shu Ding/Vercel Labs’ gpu-lexer** and **Arik Chakma’s gpu-time**. Both have approximately forty thousand learned parameters, browser inference implementations, and PyTorch training code that supports Apple MPS. Desert Ant Labs spans a much broader range: from small classifiers to compressed pretrained encoders and speech systems hundreds of megabytes in size. These projects should not all be treated as the same kind of training problem.[^1][^4][^5][^8][^10]

**Needle 2 is a particularly relevant middle ground:** a 45M-parameter tool-calling model, compressed to approximately 14 MB, with browser WASM deployment and an explicit Apple Silicon fine-tuning path. Adapting its existing weights to a small tool catalogue is a realistic Mac experiment; reproducing its complete original training is not established by the public fine-tuning package.[^43][^44]

**Scope and confidence.** Project status and repository contents were checked on September 14, 2026. Published model measurements below are the authors’ results, not independent benchmarks. Hardware recommendations are engineering estimates for an M1 Pro/16 GB, not measured training times on that machine. “Build a similar model,” “fine-tune an existing model,” and “exactly reproduce the published checkpoint” are separate claims throughout this report.

**The main projects at a glance**

| Project | Learned task | Published deployment size | Browser execution | M1 Pro/16 GB assessment |
|---|---|---|---|---|
| gpu-lexer | Assign syntax colors to source fragments | 41,321 deployed weights; complete package 27.46 KiB Brotli | Custom WebGPU | Strong candidate; MPS explicitly supported |
| gpu-time | Tag time expressions, then resolve schedules | 38,745 parameters; complete package 44,682 bytes Brotli | JavaScript CPU or custom WebGPU | Strong candidate for new training; released checkpoint lineage is incomplete in a clean clone |
| Needle 2 | Tool calling and structured extraction | 45M parameters; approximately 14 MB deployed binary | Official WASM export; independent needle-rs runtime | LoRA fine-tuning is plausible; use the pinned JAX-Metal stack and benchmark locally |
| Desert Ant Shapes | Recognize a single drawn shape | 200 KB Core ML; 1.3 MB LiteRT | LiteRT.js/WASM | Similar narrow classifier is realistic; exact training recipe not established |
| Desert Ant Tongue | Identify text language | Approximately 2 MB int8; 1 MB int4 option | Pure JavaScript | Very suitable model family; broad language data is the harder part |
| Desert Ant Emo | Suggest emoji from short text | Approximately 5 MB Apple; 11 MB LiteRT including tokenizer | LiteRT.js/WASM | Pretrained static embeddings plus a classifier are a practical route |
| Desert Ant Redact | Find personal-information spans | 23M parameters; 11.6 MB Core ML; 24.5 MB LiteRT model | LiteRT.js/WASM | Small-batch fine-tuning is plausible; multilingual data production is substantial |
| Model2Vec/Potion | Produce static text embeddings | Small models around 8–30 MB in float32 | ONNX/Transformers.js exports available | Excellent starting point; basic distillation works on CPU |
| Google Magika | Identify file content types | A few MB, version dependent | JavaScript browser binding | A reduced task is feasible; production-scale reproduction is much more demanding |

Sizes above describe different things: compressed complete packages, model files, or model-plus-tokenizer bundles. They are explicitly labelled rather than presented as directly comparable downloads.[^1][^5][^11][^12][^14][^16][^29][^30][^31][^43]

**What makes these models small**

The common design is to assign the model a restricted prediction task. A classifier chooses a label; a token tagger assigns roles; a small decoder emits a compact command. Ordinary software performs exact operations such as date arithmetic, drawing geometry, grouping spans, validating identifiers, or expanding repetitions. This reduces the amount of behavior the model must learn.

There are four distinct construction methods:

| Method | What is learned or changed | Representative projects | What the builder needs |
|---|---|---|---|
| Train a narrow model from scratch | Small weights for a constrained task | gpu-lexer, gpu-time; Tongue states it is trained from scratch | Labels, a small trainer, useful evaluation data |
| Reuse representations and train a task classifier | A small head, sometimes with further adaptation of embeddings | Emo, Gist; Model2Vec classifiers | Pretrained embeddings and task-labelled examples |
| Fine-tune and compress a pretrained network | Adapt existing language/audio/vision knowledge | Redact, Clear, Uhm, Title, Moderator | Base checkpoint, task dataset, more compute and export work |
| Extract and package an existing capability | Remove unused operations and optimize deployment | Ear; Voz primarily converts/compresses its upstream model | Conversion tools, runtime engineering, parity testing |

The upstream pretraining cost is inherited in the last three approaches. It does not have to be paid again to make a useful derivative. Conversely, a small output file does not tell us how much data or compute was used to produce it.[^13][^15][^17][^20][^21][^22][^24][^25]

**gpu-lexer: learning the output of an existing tool**

The useful insight is to use an established syntax highlighter as a label generator. The shipped checkpoint has 41,609 training parameters; deployment removes unused weights, leaving 41,321. Its reported verification result is 88.02% agreement with normalized Shiki labels and 79.09% styled macro F1. This is an approximation for visual coloring, not a language parser or a semantics engine.[^1]

At inference, a CPU pass mechanically splits source into word runs, whitespace, newlines, and symbols. Compact features describe things such as spelling hashes, length, edge characters, and nearby punctuation. A 32-channel model combines local evidence with bidirectional scans and a shared binary tree that carries broader context. A small classifier assigns nine visual categories; JavaScript reconstructs colored spans.[^2]

The training pipeline collects pinned, permissively licensed source repositories and npm packages. Shiki supplies supervision offline, so Shiki and its grammar catalogue do not ship in the browser runtime. The promoted run’s natural corpus pass contains roughly 4.68 million prepared parts. Training, verification, and mining are separated by repository/package, reducing leakage from related files.[^1][^3]

The repository also includes quantization-aware training, auxiliary lexical-state objectives, replay of difficult examples, and language-specific regression checks. Training retains float weights while simulating deployment precision; the browser representation uses six-bit weights. Promotion evaluates the quantized candidate and prevents a pooled improvement from hiding configured language regressions.[^2][^3]

**Mac feasibility:** this is unusually direct. The runtime selector explicitly checks MPS, then CUDA, and can use an explicitly requested CPU. The trainer handles MPS synchronization and memory cleanup. It also exposes batch-token and corpus-size controls; the default accelerator batch selection tests large batches, so a small model is not a guarantee that every default configuration fits comfortably.[^4]

No attributable training-machine specification or end-to-end training duration was established for the released checkpoint. The evidence supports training this architecture on Apple Silicon, not a claim that the published checkpoint took a particular number of minutes on an M1 Pro. Its clean-clone starting point is better than many demos: promoted float and quantized weights are tracked, and ordinary training resumes them. A fresh run is a separate experiment.[^1][^3]

**gpu-time: learn temporal roles, keep the calendar in code**

This is the closest match to the unnamed date-parsing example. It handles short English expressions and can return dates, ranges, and recurrence rules. The caller supplies a reference instant and timezone. Small requests normally use the CPU; the automatic backend considers WebGPU at 32 inputs or 512 tokens per batch. This acknowledges that GPU submission costs can dominate tiny requests.[^6]

The model predicts temporal roles and expression boundaries. A CRF transition table and Viterbi decoder favor coherent role sequences. The compiler interprets those roles; a separate resolver applies timezone and daylight-saving rules. The active configuration has two scan layers and 38,745 parameters, with six-bit weights. The architecture therefore combines learned language interpretation with an explicit calendar implementation.[^5][^7]

Training is largely procedural. The generator starts with semantic slots and renders phrases while preserving label spans. It reserves alternative frames for held-out generation. Real English is harvested from Tatoeba, and the model card describes agreement-filtered labels plus 1,004 written teacher examples. The shipped run uses 60,000 generated rows, while the generator’s default is 300,000. Negative examples matter: a month used as a person’s name and an ordinal in an address must not silently become dates.[^5][^9]

The reported benchmarks need careful interpretation. The card includes 5,791/6,011 exact schedules on its real-English corpus holdout, but only 229/563 agreement with Microsoft Recognizers development cases. Different interpretation policies contribute to failures. Authored regression suites and generated held-outs do not establish reliability on arbitrary user input. The card also records unresolved cases and a full benchmark blocked by legacy oracle rows.[^5]

**Mac feasibility:** the trainer defaults to MPS when available and otherwise CPU. Some decoding deliberately moves off MPS because the reference comparison uses float64. This is useful evidence that Apple behavior was considered rather than merely assumed portable.[^8]

**Reproducibility is the larger obstacle.** The documented continuation command refers to local `.pt` checkpoints that Git does not contain. Committed reports and parity fixtures permit inspection and inference verification, but do not recreate all ancestor training and checkpoint averaging. A new model in this family is feasible; exactly rebuilding the shipped weights from the advertised command is not established.[^6]

**Needle 2: a small generative model with a purpose-built runtime**

Needle 2 sits between token classification and general-purpose language models. It reads a query and tool schemas, then generates a structured call. The official package combines a 45M-parameter model with CQ2-bit compression, schema-constrained decoding, tool retrieval, and a bounded context cache. Its stated native session memory is approximately 28 MB; that is an inference measurement, not a training-memory requirement.[^43]

**Architecture and compression.** The Simple Attention Network design replaces a conventional large feed-forward block with a Hadamard-based component, alongside grouped-query attention, hashed n-gram memory, and multiple residual streams. The fixed transform reduces learned dense weight storage. Low-bit compression and a specialized engine then reduce deployment cost further. The released architecture implementation makes this inspectable; the model is not simply a conventional transformer saved as a smaller ZIP file.[^45]

Schema constraints can rule out malformed calls or undeclared tool names, but cannot prove that a selected tool or argument matches the request. For example, a temperature within an allowed range can still be the wrong temperature. This also explains why the timer-planner lesson does not mean “never generate JSON”: constrained decoding changes the format burden, while application-level correctness still needs evaluation.

**What its published training workflow actually does.** The package freezes the base model and fits rank-16 LoRA adapters to five attention projections per layer. JSONL examples contain the query, tools, expected calls, and optionally a short derivation. Adapters are merged at export. Current fine-tuning is quantization-aware by default, targets the checkpoint’s export scheme, and runs float32 training across backends.[^44][^45]

The repository includes optional teacher-assisted data generation. It is useful for augmenting examples for a particular tool catalogue, but is not evidence that the same generator and dataset produced all of Needle 2’s original capabilities. The inspected public package establishes inference, adaptation, and export much more clearly than complete base-model pretraining provenance.[^45]

**On the M1 Pro/16 GB:** adapting this model is a reasonable experiment. Current installation uses `cactus-needle[train,metal]`; the Metal extra pins JAX/JAXLIB to 0.4.38. The implementation switches to manual attention, disables rematerialization, and unrolls the layer stack for Metal. Those backend-specific choices matter as much as the parameter count.[^45]

The maintainer documents **0.71 seconds per training step on M5 Max versus 2.90 seconds on CPU at the same shape**, plus about 23 seconds of initial compilation. These are not M1 timings. For a first experiment, use short examples and a small batch, confirm the selected backend, and time a complete training/evaluation cycle. The guide suggests hundreds of examples for tool selection and thousands for stronger argument grounding. It also disables the base confidence score after fine-tuning because that head is not recalibrated.[^44]

There is conflicting historical experience: a separate PostTrainLLM experiment reports a JAX-Metal attention compilation failure on an M5 Pro. Current upstream code contains explicit Metal workarounds, so that report should be treated as version-specific evidence, not proof that today’s path cannot work. Conversely, the new M5 Max result is not a guarantee for an untested M1 environment.[^45][^46]

**Browser support is real, but identify the route.** The official model release lists `needle.js` and `needle.wasm`. Independently, needle-rs now supports both v1 and v2 and describes v2 as a 13.7 MB model plus a 413 KB WASM runtime. Older search results describing a 26M encoder–decoder concern Needle v1. Also, the official Python `needle playground` is a browser UI backed by a local server; it should not be confused with execution inside the browser tab.[^43][^47][^48]

**Original training hardware remains unverified.** The linked SAN paper reports eight H100 80 GB GPUs for its architecture study, with some seven-GPU phases. It does not identify those runs as the exact released 45M Needle 2 checkpoint. It would be incorrect to say “Needle 2 requires eight H100s.” The defensible conclusion is: local LoRA adaptation is documented; complete foundation-training compute and data for this particular release were not established.[^49]

For a concrete extreme deployment example, an independent ESP32-S3 port reports roughly 1.87 tokens/second and about 25 seconds per request with reasoning off. That is useful evidence that fitting into tiny hardware and meeting an interactive latency target are separate achievements.[^50]

**Desert Ant Labs: a catalogue of different techniques**

The SDK and model cards reveal a practical product strategy: separate narrow capabilities, reuse pretrained components where useful, and provide platform-specific exports. However, the public SDK is principally deployment code. The public GitHub organisation and inspected Hub files did not establish complete training repositories for every model. Architectural provenance is often much clearer than the exact training schedule or hardware.[^10]

The current catalogue also contains Apple-only products and closed betas. Having a page, an ONNX file, or a browser-sounding description is not equivalent to a supported browser SDK. The following inventory preserves those distinctions.

| Model | What the public material establishes | Deployment/status and implications |
|---|---|---|
| **Shapes** | Single-stroke input; six classes including rejection; fitted vector geometry. Input export is a fixed points/features window and mask. | Browser SDK available. 200 KB Apple artifact versus 1.3 MB LiteRT. Strong candidate for a similar first project; training corpus and full recipe were not established. [^11] |
| **Tongue** | Character-ngram hashing, learned lexical classification, and script routing. 59 languages are learned; another 25 are routed by script. Explicitly trained from scratch. | Pure JavaScript, approximately 2 MB int8, no tokenizer or WASM runtime required. Its training data includes Tatoeba, Common Voice text, lexemes, dictionaries, and selected treebanks. [^12][^13] |
| **Emo** | Distribution over 812 emoji, optimized for short intent-like text across 22 languages. Reuses MinishLab semantic embeddings; CLDR annotations ground training examples. | Browser model plus tokenizer around 11 MB. A realistic path is to reuse embeddings and train a smaller vocabulary of task labels first. [^14][^15] |
| **Gist** | Static multilingual embeddings feed a 36-topic classifier. English and multilingual variants are documented. | Browser SDK exists, but JS currently selects the multilingual build. The approximately 15 MB English figure must not be presented as the default JS download; multilingual assets are substantially larger. [^18] |
| **Redact** | MiniLM truncated to six layers, vocabulary trimmed, then fine-tuned for BIOES personal-information tagging. Structured identifiers also use deterministic logic. | Browser model 24.5 MB int8, versus 11.6 MB Apple. Public and synthetic datasets plus teacher-labelled web text contribute to training. [^16][^17] |
| **Ear** | Retains Whisper-tiny’s language-identification capability and removes parameters not needed for the task. Host software prepares audio features and selects windows. | Browser SDK; 22 MB LiteRT versus 13 MB Core ML. Useful example of extracting an existing capability rather than training a recognizer from scratch. [^19] |
| **Clear** | Two fine-tuned DeepFilterNet 3 variants, using the DFN3-half configuration and a Desert Ant speech corpus. | Browser SDK available. Published Apple/ONNX sizes are 9/24 MB per variant; these are different exports, not a universal browser bundle size. [^20] |
| **Uhm** | Fine-tuned DistilHuBERT detects filler sounds. AMI Meeting Corpus is named among fine-tuning sources. | A 51 MB fp16 ONNX browser artifact is documented; Apple model is 45 MB. Multilingual transfer is acoustic and not equivalent to per-language validation. [^21] |
| **Clips** | XLM-R base fine-tuned end to end with selection and scoring heads on internal editorial transcripts and decisions. | Approximately 284 MB Apple package; separate LiteRT graphs are large. Current SDK catalogue does not list browser support. Exact training data is private. [^23] |
| **Title** | Fine-tuned Granite 4.0 350M, packaged with six-bit weights for brief titles and descriptions. | Apple MLX product. Current SDK does not provide a browser build. This is a small generative model, a different scale from the two forty-thousand-parameter parsers. [^22] |
| **Voz** | Derived from Parakeet TDT 0.6B v3; converted to Core ML, graph-restructured and six-bit compressed. Notices say weight values otherwise remain unchanged. | Apple only, approximately 467 MB. Its speed reflects runtime/conversion engineering and upstream recognition capabilities. [^24] |
| **Align** | Two small stages plus a gradient-boosted calibration component refine word timestamps from Apple SpeechAnalyzer. | Apple only; approximately 0.3 MB per neural stage plus sidecars. Depends on the Apple speech pipeline and newer OS APIs. [^26] |
| **Schemer** | Pruned mmBERT encoder and type-specific heads extract caller-specified structured fields; deterministic postprocessing handles values. | Closed beta. Card lists 211M parameters, a 111 MB int4 encoder and additional decoding/tokenizer assets. The encoder size is not the full browser download. [^27] |
| **Toxic / Toxic-en** | Multilingual and English specialist classification variants. Multilingual notices describe an XLM-R lineage, vocabulary trimming, labelled corpora, and generated examples. | Closed-beta catalogue entry; browser ONNX artifact documented. Card and notices disagree on vocabulary size, so an exact current training configuration should not be inferred from them alone. [^28] |
| **Moderator** | MobileNetV4-Conv-Medium fine-tuned with three heads; licensed imagery and generated training examples are documented. | Closed beta; 35 MB float32 ONNX and smaller Apple variants. A comparable transfer-learning task is plausible on the Mac; reproducing corpus coverage is separate. [^25] |
| **Eye, Face, Who** | Advertised frame scoring, face matching, and speaker labelling. Public detail is uneven; Who’s inspected card is effectively a placeholder. | Closed beta; insufficient evidence for defensible training-hardware estimates or a complete build recipe. [^10] |

**The useful provenance is sometimes in the notices.** Emo’s notices identify its Model2Vec/Potion lineage; Redact names the base encoder, teacher models, and datasets; Clear identifies DeepFilterNet; Voz explicitly describes conversion rather than a new acoustic-model training run. These details explain much more about build cost than the headline model size.[^15][^17][^20][^24]

A caveat about rapidly changing metadata: Emo’s notices describe a 112-dimensional reduced semantic stream, while current runtime metadata has a 128-dimensional semantic field. This report relies on the documented lineage and exported interface, and does not claim those two descriptions define one exact current architecture. Similar inconsistencies make version pinning essential before reproducing a model.[^15][^41]

**Seven additional examples worth studying**

**1. Google Magika — tiny inference, substantial training.** Magika identifies file types from limited byte samples rather than needing to process entire files. It has a browser binding and a production use case. Its current README describes a few-megabyte model and roughly 100 million training/evaluation samples across more than 200 content types.[^31]

The published paper gives rare concrete hardware evidence: **Ryzen 9 7950X, one RTX 4090, 126 GB RAM, and 6 days 21 hours for 30 epochs**. These figures belong to the paper’s experiment, not necessarily the current release. A small file classifier can be built on an M1 Pro; reproducing Magika’s broad dataset and final training scale is a workstation job. Magika is the strongest counterexample to assuming that a few-megabyte model must have been cheap to train.[^32]

**2. Model2Vec/Potion — inexpensive adaptation of existing language knowledge.** Basic distillation sends vocabulary entries through a pretrained sentence transformer and converts the results into static embeddings, with dimensionality reduction and other processing. The project advertises approximately 30 seconds of CPU distillation without a task corpus. This is the basic extraction/distillation step, not training the original teacher or reproducing every subsequent Potion improvement.[^29]

There is an official Potion 8M ONNX export for ONNX Runtime and Transformers.js, and a browser semantic-similarity application illustrates deployment. A topic or emoji classifier built on these representations is probably the shortest route from a dataset to a useful local text feature on this Mac.[^30]

**3. Silero VAD with ricky0123/vad — a small model inside an ordinary browser API.** The browser wrapper uses ONNX Runtime Web to detect speech boundaries. The upstream project reports training over a very broad multilingual audio corpus; its FAQ says the training code and datasets were not published. This is an excellent integration example, but not an equally complete training tutorial. Loading the weights is easy relative to reproducing their coverage.[^33]

**4. RNNoise with a WASM wrapper — learned audio cleanup plus signal processing.** Xiph publishes a training path using clean speech, noise, generated features, PyTorch checkpoints, and export into the C runtime. Jitsi provides an Emscripten/WASM build suited to web audio integration. The inspected trainer selects CUDA or CPU rather than MPS, so native Apple GPU acceleration would need investigation or adaptation. The published recipe targets roughly 75,000 updates; this is more substantial than fitting a text-classification head.[^34][^35]

**5. TensorFlow.js transfer-learning classifiers — train directly in the browser.** Google’s Teachable Machine-style codelab loads MobileNet, extracts visual features, and trains a new classifier with collected examples. This proves that a useful new classifier need not require a GPU server—or even a Python training environment. It reuses a pretrained visual backbone; it does not train MobileNet from scratch.[^36]

**6. A tiny timer planner — the output representation matters.** Maksim Ivanov’s May 2026 write-up fine-tunes T5-Efficient-tiny, about 15.57M parameters, to emit a compact timer language. Deterministic software expands repeat counts. The final reported dataset has 685 training rows and 139 validation rows, with perfect validation exact match after targeted revisions. The changing, repeatedly consulted validation sets are not evidence of universal reliability. This is a browser-oriented training case study; the article does not establish a complete audited browser release or an attributable training-machine specification.[^37]

**7. Haku Lab DateLM — an adjacent specialist, with a deployment qualification.** The write-up describes a roughly 14M-parameter decoder that emits a compact date grammar, followed by a deterministic resolver. It supports the same division of responsibilities as gpu-time. However, the inspected demo page submits text with an HTTP POST to an endpoint. The demonstration therefore does not establish browser-local inference, despite the lab’s broader on-device focus. No complete public training recipe was established from the article.[^38]

**What your M1 Pro can realistically do**

**Start with PyTorch/MPS for small custom networks.** Both target parser projects already use it, and PyTorch documents MPS as the macOS GPU backend. Check availability in the actual Python environment; macOS version and installed wheels matter. MLX is also useful, especially for supported pretrained models and LoRA fine-tuning, but changing frameworks is unnecessary when a project already has a working MPS path.[^4][^8][^39][^40]

The Neural Engine is a separate deployment concern. The verified custom training paths here use MPS on the GPU. A Core ML model running quickly on the Neural Engine does not imply that the training loop uses that hardware. Likewise, WebGPU in a browser does not provide the same execution environment as a native Core ML application.

The following estimates concern **building comparable capabilities**, not reproducing unreleased datasets or published checkpoints:

| Workload | Recommendation for M1 Pro/16 GB | When another machine helps |
|---|---|---|
| Tens-of-thousands-parameter token tagger | Train locally; use the existing MPS backend and a manageable batch | Large sweeps or a training operation with poor MPS performance |
| Small hashed-feature classifier | Train locally, including CPU baselines | Millions of examples and repeated multilingual evaluation |
| Static embeddings plus task head | Best first text project; cache or stream embeddings | Teacher is too large to fit, or bulk labelling dominates |
| Few-million-parameter stroke/image model | Local training or transfer learning is realistic | Larger image resolution, substantial augmentation, many experiments |
| 15–60M pretrained text model | Fine-tune locally with small batches and short sequences | Long contexts, full-dataset iteration speed, operator incompatibilities |
| 100–350M transformer | Prefer frozen-backbone or adapter experiments; full fine-tuning is configuration-dependent | Sustained full fine-tuning, large batches, long sequences |
| 0.5–3B generative model | Selected quantized adapter experiments can be practical | Larger context, larger batch, teacher generation throughput |
| Foundation speech/language pretraining | Reuse existing weights | Production pretraining belongs on substantially larger compute |

**Memory arithmetic explains why the tiny models fit.** As a planning calculation, a basic float32 Adam setup stores weights, gradients, and two optimizer moments: approximately `16 × parameter_count` bytes before activations and runtime overhead. That is about 0.67 MB for gpu-lexer’s training weights and states, 368 MB for 23M parameters, 960 MB for 60M, and 5.6 GB for 350M. These are not peak-memory forecasts. Activations, temporary tensors, teacher copies, dataset materialization, and evaluation can be much larger.

Your 16 GB is shared with macOS, the CPU, GPU, and other applications. A configuration that needs almost 16 GB for model tensors alone is not viable in practice. Sequence length and batch size should be reduced before assuming the model itself is too large. Quantized inference files also do not imply equivalently quantized training: ordinary and quantization-aware training frequently retain float weights and optimizer states.

**No credible exact training-time promise is available for your Mac.** Neither tiny parser provides an attributable M1 Pro/16 GB wall-clock result in the inspected evidence. The useful measurement is one representative epoch or a fixed number of updates, including periodic evaluation. Multiply observed throughput by the intended data passes, then add data preparation and export time. For iterative work, measure the time needed to test a hypothesis, not only the time spent in backpropagation.

**When to rent a GPU.** A CUDA machine becomes worthwhile when a needed trainer is CUDA-oriented, when local full fine-tuning exceeds memory, or when experiments occupy the Mac for days. A single 16–24 GB NVIDIA GPU is a reasonable next class to benchmark for many modest fine-tunes; 24–48 GB provides more room for bigger batches, models, or teachers. These are planning ranges, not universal minimums. Data workers and corpora need separate host RAM and disk; Magika demonstrates why GPU memory alone is an incomplete specification.[^32][^35]

Buying another Mac is not a prerequisite for the first project. Run one measured local training experiment before considering new hardware. If teacher generation is the bottleneck, generate labels elsewhere or use existing labelled data; the resulting student can still be trained and deployed locally.

**A practical build recipe**

**First choose a narrow product contract.** For an emoji model, start with a limited set of common intents. For a date model, specify the language, relative-date policy, timezone behavior, and rejection cases. For shapes, specify single-stroke input and a small class set. Reducing ambiguous scope often saves more work than changing the architecture.

**Create labels using the cheapest reliable source.** Existing software can supervise syntax highlighting. A semantic generator can render calendar phrases with known roles. A labelled corpus or pretrained embedding model can support classification. A large language model can supply paraphrases or labels where rules cannot, but its output needs validation. Keep the teacher offline from the final product architecture.

**Build the evaluation split before optimizing.** Separate source repositories for code, phrase families for synthetic language, speakers for audio, and original objects/subjects for images. Keep a human-written or naturally occurring test set that was not repeatedly used to adjust training. Deliberately include confusing non-examples, rather than filling the test set only with the intended feature’s positive cases.

**Train a simple baseline on the Mac.** For text labels, start with static embeddings and a linear or small neural head. For token roles, study the two tiny parser trainers. For images, reuse a compact pretrained backbone. Start with a subset that proves the complete pipeline, then expand the data. A working export and a meaningful test failure are more valuable than a large first training run.

**Keep exact operations outside the network.** A model can label “next,” “Friday,” and “3pm”; software resolves that against a reference date. A classifier can propose an ellipse; geometry code fits and checks the stroke. A tagger can find a likely personal name; explicit validators can handle well-structured identifiers. This boundary gives errors somewhere concrete to be inspected.

**Export early, optimize after correctness.** ONNX Runtime Web offers a general browser route with WASM and WebGPU backends. Its documentation distinguishes operator coverage: GPU backends support a subset, so the exact exported graph needs testing. Desert Ant’s LiteRT route is another existing option. Handwritten WGSL is appropriate when the bundle or execution pattern justifies the engineering effort; it is not required to make a first browser model.[^42]

**Measure the shipped feature.** Track complete cold download size, first-load latency, warm latency, peak memory, and task quality. Count the tokenizer and runtime along with the weights. For GPU results, include submission/readback and preprocessing rather than timing only a kernel. For date parsing, score resolved schedules; token accuracy can look excellent while one wrong token changes the appointment.

**Only then compress.** Compare float, int8, and lower-bit candidates on the same frozen test cases. Check Python-versus-browser parity. Six-bit weights are not automatically preferable to standard int8 if they require a custom runtime, and the smallest download is not necessarily the fastest execution. Maintain a clear rejection or fallback behavior for unsupported inputs.

**Recommended order for this machine**

1. **Fastest useful text experiment:** Model2Vec embeddings plus an intent, topic, or emoji classifier. It inherits semantic knowledge cheaply and avoids autoregressive generation.
2. **Best study of tiny-model engineering:** gpu-lexer. It has explicit MPS support, a pinned corpus manifest, and tracked promoted weights for continuation.
3. **Best natural-language parsing lesson:** gpu-time. Study the generators, token roles, compiler, and negative examples; plan a fresh training run rather than assuming all released ancestry is available.
4. **Best existing tool-calling model to adapt:** Needle 2, with a small catalogue and a frozen evaluation set. Validate the pinned JAX-Metal setup before expanding the dataset.
5. **Best visual first project:** a small stroke classifier, or MobileNet transfer learning if inputs are photographs.
6. **Later experiments:** small seq2seq command generation or multilingual token tagging. Audio fine-tuning and broad generative capabilities add more data and runtime complexity.

The central opportunity is a small learned component inside ordinary software. On an M1 Pro/16 GB, that is already practical. The strongest first investment is a carefully defined task and an honest held-out test set.

**Sources and version notes**

Primary sources were accessed September 14, 2026. Repository heads observed: gpu-lexer `1e514fd681e31d6b19296f985fb01d8fdc0ae74f`; gpu-time `4c5058c55a72e38d129f490297777762ba618a33`; desert-ant-core `bbc3acbee73c9160fb0fc30f86df474fe388ac39`. Hub cards and linked documentation can change independently of SDK versions. Sources without a publication date are identified by project and file rather than assigned an invented date.

Needle was inspected at `956840ff176bfe179bb2f230b726f4be44fb11cf`, with package metadata version 2.0.12. Its current Metal guidance differs from older third-party setup articles.

[^1]: Shu Ding / Vercel Labs. [gpu-lexer model card](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/MODEL_CARD.md). Promoted checkpoint dated September 9, 2026; parameter count, corpus, quality, limitations, and reproducibility.
[^2]: Vercel Labs. [gpu-lexer architecture](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/architecture.md). Preprocessing, learned context, six-bit representation, and runtime boundaries.
[^3]: Vercel Labs. [Training and promotion policy](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/WEIGHTED-TRAINING.md), [corpus documentation](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/data/README.md), and [project README](https://github.com/vercel-labs/gpu-lexer). Training workflow and continuation.
[^4]: Vercel Labs. [PyTorch runtime selection](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/torch-runner.js), [trainer](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/torch/train.py), and [training configuration](https://github.com/vercel-labs/gpu-lexer/blob/1e514fd681e31d6b19296f985fb01d8fdc0ae74f/packages/training/src/train-tree.js). MPS/CUDA/CPU and batching evidence.
[^5]: Arik Chakma. [gpu-time model card](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/MODEL_CARD.md). Model size, training mixture, benchmark qualifications, and limits.
[^6]: Arik Chakma. [gpu-time README](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/README.md). Public API, backend thresholds, and documented training checkpoint requirement.
[^7]: Arik Chakma. [gpu-time architecture](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/architecture.md). Roles, learned scans, compiler, and resolver.
[^8]: Arik Chakma. [gpu-time trainer](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/train.py) and [model implementation](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/model.py). Explicit MPS selection and CPU decoding for float64 parity.
[^9]: Arik Chakma. [Synthetic generator](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/generate.py) and [real-text harvesting](https://github.com/arikchakma/gpu-time/blob/4c5058c55a72e38d129f490297777762ba618a33/packages/training/torch/harvest.py). Semantic labels, reserved renderings, default count, Tatoeba.
[^10]: Desert Ant Labs. [Website](https://desertant.com/), [SDK catalogue](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/bbc3acbee73c9160fb0fc30f86df474fe388ac39/README.md), [public repositories](https://github.com/orgs/Desert-Ant-Labs/repositories), and [Who card](https://huggingface.co/desert-ant-labs/who). Platforms, beta status, and availability.
[^11]: Desert Ant Labs. [Shapes model card](https://huggingface.co/desert-ant-labs/shapes) and [runtime metadata](https://huggingface.co/desert-ant-labs/shapes/blob/main/shapes_meta.json). Export sizes, classes, input shape, and rejection gates.
[^12]: Desert Ant Labs. [Tongue model card](https://huggingface.co/desert-ant-labs/tongue) and [JavaScript model implementation](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/main/packages/tongue-node/src/model.ts). Character features, script routing, quantization, and runtime.
[^13]: Desert Ant Labs. [Tongue third-party notices](https://huggingface.co/desert-ant-labs/tongue/blob/main/THIRD_PARTY_NOTICES.md). From-scratch provenance, training corpora, and split policy.
[^14]: Desert Ant Labs. [Emo model card](https://huggingface.co/desert-ant-labs/emo). Emoji vocabulary, languages, exports, and tokenizer.
[^15]: Desert Ant Labs. [Emo third-party notices](https://huggingface.co/desert-ant-labs/emo/blob/main/THIRD_PARTY_NOTICES.md). Potion, BGE-M3, Model2Vec, and CLDR lineage.
[^16]: Desert Ant Labs. [Redact model card](https://huggingface.co/desert-ant-labs/redact). Parameter count, runtime sizes, and learned/deterministic components.
[^17]: Desert Ant Labs. [Redact third-party notices](https://huggingface.co/desert-ant-labs/redact/blob/main/THIRD_PARTY_NOTICES.md). MiniLM modifications, teacher models, public corpora, and synthetic data.
[^18]: Desert Ant Labs. [Gist SDK/model documentation](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/main/docs/models/gist.md). Static embeddings, 36-topic head, variants, export sizes, and JS limitations.
[^19]: Desert Ant Labs. [Ear model card](https://huggingface.co/desert-ant-labs/ear). Whisper-tiny derivation, audio preprocessing, files, and languages.
[^20]: Desert Ant Labs. [Clear card](https://huggingface.co/desert-ant-labs/clear) and [third-party notices](https://huggingface.co/desert-ant-labs/clear/blob/main/THIRD_PARTY_NOTICES.md). DeepFilterNet 3 fine-tunes and deployment files.
[^21]: Desert Ant Labs. [Uhm model card](https://huggingface.co/desert-ant-labs/uhm). DistilHuBERT, AMI corpus, browser ONNX export, and language limitations.
[^22]: Desert Ant Labs. [Title documentation](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/main/docs/models/title.md). Granite 350M base, six-bit MLX export, Apple-only SDK, and limitations.
[^23]: Desert Ant Labs. [Clips card](https://huggingface.co/desert-ant-labs/clips) and [third-party notices](https://huggingface.co/desert-ant-labs/clips/blob/main/THIRD_PARTY_NOTICES.md). XLM-R backbone, internal training data, export sizes.
[^24]: Desert Ant Labs. [Voz documentation](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/main/docs/models/voz.md) and [third-party notices](https://huggingface.co/desert-ant-labs/voz/blob/main/THIRD_PARTY_NOTICES.md). Parakeet derivation, conversion/compression, Apple runtime.
[^25]: Desert Ant Labs. [Moderator card](https://huggingface.co/desert-ant-labs/moderator) and [third-party notices](https://huggingface.co/desert-ant-labs/moderator/blob/main/THIRD_PARTY_NOTICES.md). MobileNetV4 fine-tuning and dataset provenance.
[^26]: Desert Ant Labs. [Align documentation](https://github.com/Desert-Ant-Labs/desert-ant-core/blob/main/docs/models/align.md). Two neural stages, calibration, Apple dependencies, and sizes.
[^27]: Desert Ant Labs. [Schemer model card](https://huggingface.co/desert-ant-labs/schemer). Encoder, structured heads, complete export components, and parameters.
[^28]: Desert Ant Labs. [Toxic card](https://huggingface.co/desert-ant-labs/toxic) and [third-party notices](https://huggingface.co/desert-ant-labs/toxic/blob/main/THIRD_PARTY_NOTICES.md). Architecture/data descriptions and their vocabulary-count discrepancy.
[^29]: MinishLab. [Model2Vec repository](https://github.com/MinishLab/model2vec) and [authors’ introduction](https://huggingface.co/blog/Pringled/model2vec), October 2024. CPU distillation, static representations, sizes, classifier training, and limitations of the timing claim.
[^30]: MinishLab. [Potion 8M ONNX model](https://huggingface.co/minishlab/potion-base-8m-onnx). Browser-compatible export. Dominik Meißner. [Semantic Similarity Table](https://github.com/do-me/semantic-similarity-table), browser application.
[^31]: Google. [Magika repository](https://github.com/google/magika) and [JavaScript binding](https://github.com/google/magika/tree/main/js). Current deployment, task coverage, and data scale.
[^32]: Fratantonio et al. [Magika: AI-Powered Content-Type Detection](https://arxiv.org/html/2409.13768v1), 2024 preprint, subsequently ICSE 2025. Section V-C: exact training machine and 6-day-21-hour run; other sections describe byte features and evaluation.
[^33]: Silero Team. [Silero VAD](https://github.com/snakers4/silero-vad) and [FAQ](https://github.com/snakers4/silero-vad/wiki/FAQ); Ricky0123. [Browser VAD](https://github.com/ricky0123/vad). Broad audio training claim, unavailable full recipe, browser wrapper.
[^34]: Xiph. [RNNoise training README](https://github.com/xiph/rnnoise/blob/main/README) and [PyTorch trainer](https://github.com/xiph/rnnoise/blob/main/torch/rnnoise/train_rnnoise.py). Public training procedure and CUDA/CPU selection.
[^35]: Jitsi. [RNNoise WASM](https://github.com/jitsi/rnnoise-wasm). Emscripten build and web audio packaging. Hardware planning discussion also draws on the trainer in source 34.
[^36]: Google. [Make your own Teachable Machine using TensorFlow.js](https://codelabs.developers.google.com/tensorflowjs-transfer-learning-teachable-machine). Browser-based MobileNet feature extraction and classifier training.
[^37]: Maksim Ivanov. [Training A Tiny Model To Set Timers From Natural Language](https://maksimivanov.com/posts/training-a-tiny-model-to-set-timers/), May 17, 2026. T5-Efficient-tiny, compact DSL, dataset sizes, and iterative validation results.
[^38]: Haku Lab. [Resolving natural-language dates with a tiny specialist model](https://lab.haku.sh/datelm), 2026. Model/grammar method and demo HTML’s endpoint POST.
[^39]: PyTorch. [MPS backend documentation](https://docs.pytorch.org/docs/2.14/notes/mps.html). macOS GPU execution and availability checks.
[^40]: Apple ML Explore. [MLX](https://github.com/ml-explore/mlx) and [MLX-LM LoRA guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md). Apple Silicon, fine-tuning, and memory management.
[^41]: Desert Ant Labs. [Emo runtime metadata](https://huggingface.co/desert-ant-labs/emo/blob/main/emo_meta.json). Current semantic field and architecture metadata; compare with source 15.
[^42]: ONNX Runtime. [Web deployment guide](https://onnxruntime.ai/docs/tutorials/web/). Browser backend choices, model conversion, operator coverage, and runtime size.
[^43]: Cactus Compute. [Needle 2 README](https://github.com/cactus-compute/needle/blob/956840ff176bfe179bb2f230b726f4be44fb11cf/README.md). Model size, native inference memory, retrieval, and local-server playground.
[^44]: Cactus Compute. [Needle fine-tuning guide](https://github.com/cactus-compute/needle/blob/956840ff176bfe179bb2f230b726f4be44fb11cf/doc/finetuning.md). LoRA, data requirements, quantization awareness, M5 Max timing, and disabled confidence after adaptation.
[^45]: Cactus Compute. [Fine-tuning implementation](https://github.com/cactus-compute/needle/blob/956840ff176bfe179bb2f230b726f4be44fb11cf/needle/model/finetune.py), [architecture](https://github.com/cactus-compute/needle/blob/956840ff176bfe179bb2f230b726f4be44fb11cf/needle/model/architecture.py), and [package dependency metadata](https://github.com/cactus-compute/needle/blob/956840ff176bfe179bb2f230b726f4be44fb11cf/pyproject.toml). Metal adaptations, generator, export, architecture, and JAX version pins.
[^46]: PostTrainLLM. [Needle 45M successor factorial](https://posttrainllm.com/docs/techniques/needle2-successor-factorial/). First-party account of a specific adaptation experiment and M5 Pro backend failure; not a universal model benchmark.
[^47]: Cactus Compute. [Needle 2 model card and platform exports](https://huggingface.co/Cactus-Compute/needle2). Official WebAssembly release and deployment contract.
[^48]: Abdalrahman Ibrahim / Geekgineer. [needle-rs](https://github.com/Geekgineer/needle-rs) and [browser demo](https://needle-rs.pages.dev). Current v1/v2 distinction, 413 KB runtime, 13.7 MB v2 model, and reference parity.
[^49]: Cactus Compute researchers. [A Controlled Study of Attention-Only Transformers](https://arxiv.org/html/2607.18363v1), July 2026. Architecture-study infrastructure, Appendix H; not an identified training record for the released Needle 2 checkpoint.
[^50]: Andris Gauracs. [Needle 2 on ESP32-S3](https://github.com/andrisgauracs/needle-2-esp32). Independent runtime and measured microcontroller latency.
