# Launch video

Render a silent 20-second 1920×1080 / 30 fps MP4:

```sh
uv run video/render.py
```

Requires FFmpeg. The script uses an isolated Pillow dependency, downloads the
website's Instrument Serif and Geist Mono fonts with their OFL licenses, and
writes `gpu-postal-launch-v5.mp4` and five review frames into ignored
`runs/launch-video/`. The first draft is preserved separately.
No app dependencies or production website changes.

The metrics slide reads release evidence directly: model-only Brotli size,
warm browser median (Chrome 153 / M1 Pro), and 828/842 whole-address matches on
the NAD evaluation. It explicitly notes unknown training overlap; this is not
an unseen-data accuracy claim. Metric columns use staggered left-to-right wipes.

The examples are recorded predictions, not a live browser recording. `cases.json`
records the comma-free Vercel HQ and OpenAI addresses, source URLs, model hash and
outputs verified in the live Chrome WebGPU demo on September 18, 2026.
Vercel's own Builder Day page identifies its HQ including Floor 3.
The first draft's shuffled Acadia example did not reproduce in the live demo;
the v2 cut no longer uses the historical diagnostic export.
They are selected demonstrations, not a representative accuracy estimate.
The animation does not depict inference timing or internal activations.
Sizes refer to experimental.3, decimal kB, Brotli quality 11. See the root README
and published evaluation for measurement details.

## Reference research

- [gpu-lexer](https://github.com/vercel-labs/gpu-lexer/tree/main/video):
  Manim Community, a silent ~55-second pipeline explanation, bundled Geist Mono,
  1080p at 30 fps. Persistent tokens carry the story through successive stages.
- [gpu-time](https://github.com/arikchakma/gpu-time/tree/main/video):
  ManimGL, a 91-second 1080p / 60 fps film, exported real inference traces;
  optional local Kokoro narration and FFmpeg music/caption mixing.
- [gpu-pii](https://pii.ephraimduncan.com/): a live editor pairs colored text spans
  with extracted findings. No video asset or public production source was found
  in the inspected page or its application bundle; its video tooling is unknown.

Our cut borrows the input-to-components storytelling, not their animation
code. It prioritizes actual user-visible results over a schematic neural-network
tour. Narration, music and further formats can be added after the cut is approved.
