import { ArrowUpRight } from "lucide-react";
import { ParserDemo } from "@/components/parser-demo";
import { UsageCode } from "@/components/usage-code";
import { CopyButton } from "@/components/copy-button";
import { DitherGradient } from "@/components/dither-kit/gradient";
import { SizeComparison, CountryComparison, RobustnessComparison } from "@/components/comparisons";
import benchmarks from "@/public/benchmarks.json";
import evaluation from "@/public/evaluation-us-v1/results.json";

const repo = "https://github.com/f0rr0/gpu-postal";
const code = `import { createParser } from 'gpu-postal';

const parser = await createParser();
const { components } = await parser.parse(
  '123 Main Street, Boston MA 02110'
);
// { label: 'city', raw: 'Boston', start: 17, end: 23 }

await parser.dispose();`;

export default function Page() {
  return (
    <>
      <a
        className="fixed -top-25 left-5 z-20 bg-card p-3 focus:top-2.5"
        href="#playground"
      >
        Skip to the parser
      </a>
      <header className="mx-auto flex h-24 w-full max-w-192 items-center justify-between px-4 sm:px-8 lg:px-12">
        <a
          href="#"
          className="inline-flex items-center gap-3 font-serif text-2xl leading-tight font-normal text-balance"
          aria-label="gpu-postal home"
        >
          <span
            className="size-5 bg-[repeating-conic-gradient(var(--primary)_0_25%,transparent_0_50%)] bg-size-[8px_8px]"
            aria-hidden="true"
          />
          gpu-postal
        </a>
        <nav
          className="flex gap-4 sm:gap-6 [&_a]:inline-flex [&_a]:min-h-11 [&_a]:items-center [&_a]:gap-2 [&_a]:text-sm [&_a]:text-muted-foreground"
          aria-label="Main navigation"
        >
          <a href="#get-started">Usage</a>
          <a href={repo}>
            GitHub{" "}
            <ArrowUpRight
              aria-hidden="true"
              className="inline-block size-3.5 align-text-bottom"
            />
          </a>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-192 px-4 sm:px-8 lg:px-12">
        <section className="pt-8 pb-10" aria-labelledby="hero-title">
          <h1
            className="font-serif text-[40px] leading-[1.1] font-normal tracking-normal text-balance"
            id="hero-title"
          >
            Experimental address parsing.
          </h1>
          <p className="mt-4 text-base leading-6 text-pretty">
            Labels US address components in context. Runs locally with a
            tiny WebGPU model. Full, partial or out of order.
          </p>
          <p className="mt-3 font-mono text-xs text-muted-foreground">58.7 kB model + runtime (Brotli) · 5.2 ms warm median on M1 Pro</p>
          <div className="relative mt-8 h-4" aria-hidden="true">
            <DitherGradient
              from="white"
              direction="right"
              cell={2}
              opacity={0.45}
            />
          </div>
        </section>
        <ParserDemo />
        <section
          className="py-12"
          id="get-started"
          aria-labelledby="usage-title"
        >
          <div className="mb-4 flex min-h-11 flex-wrap items-center justify-between gap-3">
            <h2
              className="font-serif text-2xl leading-tight font-normal text-balance"
              id="usage-title"
            >
              Usage
            </h2>
            <a
              className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground"
              href={`${repo}#output`}
            >
              API reference{" "}
              <ArrowUpRight
                aria-hidden="true"
                className="inline-block size-3.5 align-text-bottom"
              />
            </a>
          </div>
          <div className="min-w-0 border border-border bg-card">
            <div className="flex items-center justify-between gap-2 border-b border-dotted border-muted-foreground/70 px-4 py-2 sm:px-5">
              <code className="font-mono text-xs wrap-anywhere">
                npm install gpu-postal@experimental
              </code>
              <CopyButton
                text="npm install gpu-postal@experimental"
                label="Copy install command"
              />
            </div>
            <UsageCode code={code} />
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground [&_a]:whitespace-nowrap [&_a]:underline">
            Returns original text and character offsets. Reuse the parser across
            calls.
          </p>
        </section>
        <SizeComparison sizes={{ ...benchmarks.sizes, ...evaluation.sizes }} />
        <CountryComparison groups={[evaluation.nad]} />
        <RobustnessComparison cohorts={evaluation.diagnostics} />
      </main>
      <footer className="mx-auto w-full max-w-192 px-4 sm:px-8 lg:px-12">
        <div className="flex flex-wrap justify-between gap-4 border-t border-dotted border-muted-foreground/70 pt-6 pb-10 text-xs text-muted-foreground [&_a]:inline-block">
          <span>
            Built by{" "}
            <a href="https://github.com/f0rr0">
              Sid Jain{" "}
              <ArrowUpRight
                aria-hidden="true"
                className="inline-block size-3.5 align-text-bottom"
              />
            </a>
          </span>
          <div className="flex gap-4 sm:gap-6">
            <a href="https://www.npmjs.com/package/gpu-postal">
              npm{" "}
              <ArrowUpRight
                aria-hidden="true"
                className="inline-block size-3.5 align-text-bottom"
              />
            </a>
            <a href={`${repo}/blob/main/THIRD_PARTY_NOTICES.md`}>
              Licenses{" "}
              <ArrowUpRight
                aria-hidden="true"
                className="inline-block size-3.5 align-text-bottom"
              />
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
