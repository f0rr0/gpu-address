"use client";

import { DitherGradient } from "./dither-kit/gradient";
import { ArrowUpRight, ChevronRight } from "lucide-react";
import { BarChart } from "./dither-kit/bar-chart";
import { Bar } from "./dither-kit/bar";
import { XAxis } from "./dither-kit/x-axis";
import { YAxis } from "./dither-kit/y-axis";
import { Grid } from "./dither-kit/grid";
import { Tooltip } from "./dither-kit/tooltip";

const models = ["gpu", "usaddress", "libpostal", "senzing", "deepparse"] as const;
const labels = {
  gpu: "gpu-postal",
  usaddress: "usaddress",
  libpostal: "libpostal",
  senzing: "Senzing",
  deepparse: "Deepparse",
};
const config = {
  gpu: { label: "gpu-postal", color: "green" },
  usaddress: { label: "usaddress 0.5.16", color: "pink" },
  libpostal: { label: "libpostal default", color: "blue" },
  senzing: { label: "Senzing v1.2", color: "orange" },
  deepparse: { label: "Deepparse BPEmb + attention", color: "purple" },
} as const;
type EvaluationGroup = {
  country: string;
  cohort: string;
  rows: number;
  models: Record<(typeof models)[number], { correct: number; percent: number; interval: number[]; field_f1: number; fields: Partial<Record<string, { rows: number; predicted: number; correct: number; f1: number }>> }>;
};
const sizeText = (bytes: number) =>
  bytes < 1e6
    ? `${(bytes / 1e3).toFixed(1)} kB`
    : `${(bytes / 1e6).toFixed(1)} MB`;

// Zero-baseline linear bars; values remain readable below pixel resolution.
export function SizeComparison({
  sizes,
}: {
  sizes: Record<string, { bytes: number }>;
}) {
  const sizeModels = ["gpu", "usaddress"] as const;
  const max = Math.max(...sizeModels.map((model) => sizes[model].bytes));
  return (
    <section
      className="border-y border-dotted border-muted-foreground/70 py-8"
      aria-labelledby="size-title"
    >
      <h2 className="font-serif text-2xl leading-tight font-normal text-balance" id="size-title">
        Two small US parsers
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-pretty text-muted-foreground">
        Model weights (Brotli quality 11) · Runtime excluded for both
      </p>
      <div className="mt-6 grid gap-4" aria-label="Model sizes, linear scale">
        {sizeModels.map((model) => (
          <div key={model}>
            <div className="mb-1 flex items-baseline justify-between gap-4 text-xs">
              <span>{labels[model]}</span>
              <span className="tabular-nums">
                {sizeText(sizes[model].bytes)} (Brotli)
              </span>
            </div>
            <div className="relative h-6 border-b border-border">
              <div
                className="absolute inset-y-0 left-0"
                style={{ width: `${(100 * sizes[model].bytes) / max}%` }}
              >
                <DitherGradient
                  from={config[model].color}
                  direction="down"
                  cell={2}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Linear scale. gpu-postal includes its browser runtime in 58.7 kB (Brotli).
        usaddress additionally requires Python, CRFsuite and feature-extraction code; those are not included above.{" "}
        <a className="underline" href="/evaluation-us-v1/results.json">
          Measurement data
        </a>
      </p>
      <details className="group/disclosure mt-4">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-2 text-xs text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
          <ChevronRight aria-hidden="true" className="size-3.5 transition-transform group-open/disclosure:rotate-90" />
          Multilingual models
        </summary>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          libpostal {sizeText(sizes.libpostal.bytes)} (Brotli) · Senzing {sizeText(sizes.senzing.bytes)} (Brotli) · Deepparse {sizeText(sizes.deepparse.bytes)} (Brotli).
          {" "}These historical measurements use Brotli quality 5, not the quality 11 comparison above.
          {" "}Includes broader language and feature coverage.{" "}
          <a className="underline" href="/benchmarks.json">Asset inventory</a>
        </p>
      </details>
    </section>
  );
}

function ResultTable({ rows }: { rows: EvaluationGroup[] }) {
  return (
    <div className="my-6 overflow-x-auto" tabIndex={0} role="region" aria-label="Exact-match results">
      <table className="w-full min-w-135 border-collapse text-xs tabular-nums">
        <caption className="pb-3 text-left text-xs leading-5 text-muted-foreground">
          Field F1 · Whole-address exact match
          <span className="block">Count / sample · 95% Wilson interval</span>
        </caption>
        <thead className="text-muted-foreground">
          <tr>
            <th className="border-b border-border py-3 pr-3 text-left font-normal" scope="col">Inputs</th>
            {models.map((m) => <th className="border-b border-border px-3 py-3 text-right font-normal" key={m} scope="col">{labels[m]}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.country}-${r.cohort}`}>
              <th className="border-b border-border py-3 pr-3 text-left font-normal" scope="row">
                US<span className="mt-1 block text-muted-foreground">Full addresses</span>
              </th>
              {models.map((m) => (
                <td className="border-b border-border px-3 py-3 text-right" key={m}>
                  <strong>{r.models[m].field_f1.toFixed(1)}% F1</strong>
                  <span className="mt-1 block">{r.models[m].percent.toFixed(1)}% exact</span>
                  <span className="mt-1 block text-xs text-muted-foreground">{r.models[m].correct} / {r.rows}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">{r.models[m].interval.map(v => Math.max(0, v).toFixed(1)).join("–")}%</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CountryComparison({ groups }: { groups: EvaluationGroup[] }) {
  const rows = groups.filter((g) => g.country === "us" && g.cohort === "complete");
  return (
    <section className="py-12" aria-labelledby="country-title">
      <h2 className="font-serif text-2xl leading-tight font-normal text-balance" id="country-title">US address benchmark</h2>
      <p className="mt-2 text-sm leading-relaxed text-pretty text-muted-foreground">
        {rows[0].rows.toLocaleString("en-US")} addresses · Whole-address exact match
      </p>
      <div className="my-6 flex flex-wrap gap-x-5 gap-y-3 text-xs">
        {models.map((m) => (
          <span key={m} className="flex items-center gap-2">
            <i aria-hidden="true" data-model={m}
              className="size-2 shrink-0 bg-[repeating-conic-gradient(var(--chart-1)_0_25%,transparent_0_50%)] bg-size-[4px_4px] data-[model=usaddress]:bg-[repeating-conic-gradient(var(--chart-5)_0_25%,transparent_0_50%)] data-[model=libpostal]:bg-[repeating-linear-gradient(45deg,var(--chart-2)_0_1px,transparent_1px_3px)] data-[model=senzing]:bg-linear-to-t data-[model=senzing]:from-chart-3 data-[model=senzing]:to-transparent data-[model=deepparse]:bg-chart-4 data-[model=deepparse]:bg-none" />
            {labels[m]}
          </span>
        ))}
      </div>
      <div className="h-65" role="img" aria-label="US whole-address exact-match comparison; numerical results below">
        <BarChart data={rows.map((r) => ({ name: "US", ...Object.fromEntries(models.map((m) => [m, r.models[m].percent])) }))} config={config} animate={false} bloom="off">
          <Grid /><XAxis dataKey="name" /><YAxis tickFormatter={(v) => `${v}%`} />
          {models.map((m, i) => <Bar key={m} dataKey={m} variant={(["dotted", "dotted", "hatched", "gradient", "solid"] as const)[i]} />)}
          <Tooltip labelKey="name" valueFormatter={(v) => `${v.toFixed(1)}%`} />
        </BarChart>
      </div>
      <details className="group/disclosure mt-6 border-t border-dotted border-muted-foreground/70 pt-4">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden text-xs text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-5 focus-visible:outline-primary">
          <ChevronRight aria-hidden="true" strokeWidth={1.5} className="size-3.5 shrink-0 transition-transform duration-150 group-open/disclosure:rotate-90" />
          Scores &amp; field breakdown
        </summary>
        <ResultTable rows={rows} />
        <p className="text-xs leading-5 text-muted-foreground">Whole-address exact match requires every field to match, with no extras. Field F1 credits correctly parsed fields and penalizes missing, wrong and extra fields.</p>
        <div className="my-6 overflow-x-auto" tabIndex={0} role="region" aria-label="Per-field F1">
          <table className="w-full min-w-120 text-xs tabular-nums">
            <caption className="pb-3 text-left text-xs leading-5 text-muted-foreground">Exact-match F1 by field</caption>
            <thead><tr><th className="border-b border-border py-3 text-left font-normal" scope="col">Field</th>{models.map(m => <th className="border-b border-border px-3 py-3 text-right font-normal" scope="col" key={m}>{labels[m]}</th>)}</tr></thead>
            <tbody>{rows.flatMap(r => (["street_address", "city", "state", "postcode"] as const).map(field => (
              <tr key={`${r.country}-${field}`}>
                <th scope="row" className="border-b border-border py-3 pr-3 text-left font-normal">US · {({street_address:"Address block",city:"Town / city",state:"State",postcode:"ZIP code"})[field]}</th>
                {models.map(m => <td key={m} className="border-b border-border px-3 py-3 text-right">{r.models[m].fields[field]?.f1.toFixed(1) ?? "—"}%</td>)}
              </tr>
            )))}</tbody>
          </table>
        </div>
      </details>
      <details className="group/disclosure mt-6 border-t border-dotted border-muted-foreground/70 pt-4">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden text-xs text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-5 focus-visible:outline-primary">
          <ChevronRight aria-hidden="true" strokeWidth={1.5} className="size-3.5 shrink-0 transition-transform duration-150 group-open/disclosure:rotate-90" />
          Method &amp; data
        </summary>
        <div className="mt-4 grid gap-3 text-xs leading-5 text-muted-foreground [&_a]:underline">
          <p>842 addresses across 40 states from the <a href="https://www.transportation.gov/gis/national-address-database">US National Address Database <ArrowUpRight aria-hidden="true" className="inline-block size-3.5 align-text-bottom" /></a>, including 118 with subaddresses. Author-run, structured-address sample; not population-representative. No partial-address cohort in this benchmark.</p>
          <p>gpu-postal experimental.3, usaddress 0.5.16, libpostal default, Senzing v1.2 and Deepparse BPEmb + attention. The current gpu-postal model was rerun on the frozen inputs; other parsers’ predictions are retained from the original evaluation. This is not a newly blind test. Training overlap with the expanded US corpus and competitors is unknown.</p>
          <p>Scored fields: address block, city, state and ZIP code. Localities join the address block; districts join the state. Case, commas and whitespace are ignored; other punctuation and repeated tokens count. Extra fields are errors.</p>
          <p>Source labels may contain mistakes. Confidence intervals describe this sample; competitor training overlap is unknown. The downloadable evidence retains the full original evaluation.</p>
          <p className="flex flex-wrap gap-x-4 gap-y-2"><a href="/evaluation-us-v1/README.md">Protocol &amp; reproduction</a><a href="/evaluation-us-v1/results.json">Scores, sizes &amp; hashes</a><a href="/evaluation-us-v1/nad-inputs.json">Labeled inputs</a><a href="/evaluation-us-v1/nad-gpu.json">gpu-postal predictions</a><a href="/evaluation-v4/usaddress.json">usaddress predictions</a><a href="/evaluation-us-v1/nad-browser-parity.json">WebGPU verification</a></p>
        </div>
      </details>
    </section>
  );
}

const diagnosticLabels: Record<string, string> = {
  complete: "Complete",
  shuffled: "Shuffled",
  partial: "Partial",
  "partial-shuffled": "Partial + shuffled",
  singleton: "Single field",
  "lowercase-no-commas": "Lowercase, no commas",
  "uppercase-multiline": "Uppercase, multiline",
  "typo-street": "Street-name typo",
  "typo-city": "City-name typo",
  "messy-partial-shuffled": "Messy + partial + shuffled",
  "building-prefix": "Building prefix",
  "unit-first": "Unit first",
  "natural-us50": "Historical US50 sample",
};

export function RobustnessComparison({ cohorts }: {
  cohorts: Record<string, { rows: number; gpu: number; usaddress: number }>;
}) {
  const highlighted = ["shuffled", "partial", "partial-shuffled"];
  return (
    <section className="border-t border-dotted border-muted-foreground/70 py-12" aria-labelledby="robustness-title">
      <h2 id="robustness-title" className="font-serif text-2xl leading-tight font-normal text-balance">When the order changes</h2>
      <p className="mt-2 text-sm leading-relaxed text-pretty text-muted-foreground">
        The same address facts, with fields shuffled or removed. gpu-postal keeps more of these inputs intact; usaddress leads on conventional building and unit formats.
      </p>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Synthetic variants of 20 public institutional addresses—not hundreds of independent addresses. All seven fields must match; locality is not merged into street.
      </p>
      <div className="my-6 flex gap-5 text-xs"><span className="text-chart-1">gpu-postal int5</span><span className="text-chart-5">usaddress 0.5.16</span></div>
      <div className="h-65" role="img" aria-label="Shuffled and partial address comparison; all numerical results follow">
        <BarChart data={highlighted.map(key => ({ name: diagnosticLabels[key], gpu: 100 * cohorts[key].gpu / cohorts[key].rows, usaddress: 100 * cohorts[key].usaddress / cohorts[key].rows }))} config={{ gpu: config.gpu, usaddress: config.usaddress }} animate={false} bloom="off">
          <Grid /><XAxis dataKey="name" /><YAxis tickFormatter={v => `${v}%`} />
          <Bar dataKey="gpu" variant="dotted" /><Bar dataKey="usaddress" variant="hatched" />
          <Tooltip labelKey="name" valueFormatter={v => `${v.toFixed(1)}%`} />
        </BarChart>
      </div>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-xs tabular-nums">
          <caption className="pb-3 text-left text-muted-foreground">Whole-input field match · Correct / cases</caption>
          <thead><tr><th scope="col" className="border-b border-border py-3 text-left font-normal">Input</th><th scope="col" className="border-b border-border py-3 text-right font-normal">gpu-postal</th><th scope="col" className="border-b border-border py-3 text-right font-normal">usaddress</th></tr></thead>
          <tbody>{Object.entries(diagnosticLabels).map(([key, label]) => (
            <tr key={key}>
              <th scope="row" className="border-b border-border py-3 pr-2 text-left font-normal">{label}</th>
              {(["gpu", "usaddress"] as const).map(model => <td key={model} className="border-b border-border py-3 pl-2 text-right">{(100 * cohorts[key][model] / cohorts[key].rows).toFixed(1)}%<span className="mt-1 block text-muted-foreground">{cohorts[key][model]} / {cohorts[key].rows}</span></td>)}
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="mt-4 text-xs leading-5 text-muted-foreground">
        On the full 680-address upstream usaddress US50 test, shared coarse-field matches are 675/680 (99.26%) for gpu-postal and 678/680 (99.71%) for usaddress. That scorer merges locality into street and district into state; it differs from the table above. There are 16 exact matches with our training corpus, and competitor exposure is unknown.
      </p>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Case, commas and whitespace are ignored. The institutional labels were authored before pilot inference; these cases were inspected during development. No pooled accuracy or confidence interval is claimed for correlated variants.{" "}
        <a className="underline" href="/evaluation-us-v1/diagnostic-predictions.json">Every input and both predictions</a>{" · "}<a className="underline" href="/evaluation-us-v1/README.md">Method and sources</a>
      </p>
    </section>
  );
}
