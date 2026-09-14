# Research and experiments

The current project is postal-address parsing. Start with the [project README](../README.md) for setup and commands.

| Read | Purpose |
| --- | --- |
| [Next experiments](address-next-research-plan.md) | Current evidence and proposed accuracy improvements |
| [Source-quality audit](address-source-quality-audit.md) | Data mapping, exclusions and expanded-corpus results |
| [Training results](address-training-results.md) | Earlier runs, failures and runtime checks |
| [Stack review](python-stack-deep-review.md) | Tooling decisions and measured constraints |
| [GPU Lexer / GPU Time audit](gpu-reference-tooling-audit.md) | Lessons from the reference implementations |
| [Wasm / WebGPU research](wasm-webgpu-research.md) | Browser deployment and measurement methodology |

## Supporting research

[Accuracy experiments](address-accuracy-improvements.md), [additional data sources](additional-labeled-address-sources.md), [framework comparison](training-framework-audit.md), [reference build notes](build-notes.md), and [original research](research.md).

## Historical proposals

These preserve earlier reasoning; they do not describe the current implementation:

- [Original tooling proposal](python-project-tooling.md), superseded by the stack review.
- [Phone/address plan](phone-postal-experiments.md) and [data methodology](phone-postal-data-and-evaluation.md). Phone-model work is inactive.
- [Legacy experiment commands](legacy-experiment.md), superseded by the project README.
- Earlier ideas: [interactive](interactive-opportunities.md), [focused](focused-use-cases.md), [product](opportunities.md), [web development](webdev-opportunities.md), [parsers](project-ideas.md), and [first experiment](first-experiment.md).
