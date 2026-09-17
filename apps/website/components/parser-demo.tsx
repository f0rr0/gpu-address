"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import type { ParseResult, createParser } from "gpu-postal";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Field, FieldLabel } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { rebaseAddress } from "@/lib/rebase-address";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

const samples = ([
  // Public contact addresses; these are examples, not benchmark inputs.
  // https://openai.com/policies/developer-apps-terms/
  ["OpenAI", ["1455 3rd Street", "San Francisco", "CA", "94158"]],
  // https://assets.anthropic.com/m/4e20a4ab6512e217/original/anthropic-response-to-stp-rfi-march-2025-final-submission-v3.pdf
  ["Anthropic", ["548 Market St. PMB 90375", "San Francisco", "CA", "94104-5401"]],
  // https://cloud.google.com/events/google-ai-summit
  ["Google", ["1600 Amphitheatre Pkwy", "Mountain View", "CA", "94043"]],
  // https://allenai.org/contact
  ["Ai2", ["3800 Latona Ave NE Suite 300", "Seattle", "WA", "98105"]],
] as const).map(([label, parts]) => ({
  label,
  parts,
  address: parts.join(" "),
}));
const sampleFields = ["street_address", "city", "state", "postcode"] as const;
const highlightClass =
  "bg-transparent bg-[radial-gradient(circle,color-mix(in_srgb,var(--highlight)_25%,transparent)_0.7px,transparent_0.7px)] bg-size-[3px_3px] underline decoration-2 underline-offset-4 box-decoration-clone";
type Parser = Awaited<ReturnType<typeof createParser>>;
const names: Record<string, string> = {
  street_address: "Street address",
  locality: "Locality",
  city: "City",
  district: "District",
  state: "State",
  postcode: "ZIP code",
  country: "Country",
};

const fieldColors: Record<string, { text: string; highlight: string }> = {
  street_address: {
    text: "text-chart-1",
    highlight: "[--highlight:var(--chart-1)] decoration-chart-1",
  },
  city: {
    text: "text-chart-2",
    highlight: "[--highlight:var(--chart-2)] decoration-chart-2",
  },
  state: {
    text: "text-chart-3",
    highlight: "[--highlight:var(--chart-3)] decoration-chart-3",
  },
  postcode: {
    text: "text-chart-4",
    highlight: "[--highlight:var(--chart-4)] decoration-chart-4",
  },
  locality: {
    text: "text-chart-5",
    highlight: "[--highlight:var(--chart-5)] decoration-chart-5",
  },
  district: {
    text: "text-chart-6",
    highlight: "[--highlight:var(--chart-6)] decoration-chart-6",
  },
  country: {
    text: "text-chart-7",
    highlight: "[--highlight:var(--chart-7)] decoration-chart-7",
  },
};

export function ParserDemo() {
  const [text, setText] = useState<string>(samples[0].address);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [composing, setComposing] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const parser = useRef<Parser | null>(null);
  const sequence = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let owned: Parser | null = null;
    async function initialize() {
      try {
        const { createParser } = await import("gpu-postal");
        owned = await createParser("/model-int5.bin.br");
        if (cancelled) {
          await owned.dispose();
          return;
        }
        parser.current = owned;
        setReady(true);
      } catch (cause) {
        if (!cancelled) {
          setReady(false);
          setError(
            cause instanceof Error
              ? cause.message
              : "Could not initialize WebGPU.",
          );
        }
      }
    }
    void initialize();
    return () => {
      cancelled = true;
      sequence.current++;
      parser.current = null;
      void owned?.dispose();
    };
  }, []);

  function edit(value: string) {
    sequence.current++;
    setResult((current) => rebaseAddress(current, text, value));
    setText(value);
    if (ready) setError("");
  }

  useEffect(() => {
    if (!ready || composing || !text.trim()) {
      setBusy(false);
      return;
    }
    const ticket = ++sequence.current;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      try {
        const parsed = await parser.current!.parse(text);
        if (ticket !== sequence.current) return;
        setResult(parsed);
        setError(
          parsed.status === "unsupported"
            ? "Try a shorter address: up to 512 characters, 128 tokens and 64 bytes per token."
            : "",
        );
      } catch (cause) {
        if (ticket !== sequence.current) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not parse this address.",
        );
      } finally {
        if (ticket === sequence.current) setBusy(false);
      }
    }, 200);
    return () => {
      window.clearTimeout(timer);
      sequence.current++;
    };
  }, [text, ready, composing]);

  const parts = result?.components ?? [];
  const fields = Object.keys(names);
  return (
    <section id="playground" aria-labelledby="playground-title">
      <div className="mb-4 flex min-h-11 flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2
          className="font-serif text-2xl leading-tight font-normal text-balance"
          id="playground-title"
        >
          Try a full address
        </h2>
        <p id="address-guidance" className="text-sm leading-relaxed text-pretty text-muted-foreground">
          Isolated place names can be ambiguous.
        </p>
      </div>
      <Field data-invalid={!!error}>
        <FieldLabel className="sr-only" htmlFor="address">
          Address
        </FieldLabel>
        <div className="relative border border-border bg-card focus-within:border-ring">
          <div
            data-slot="address-highlights"
            aria-hidden="true"
            className="pointer-events-none min-h-20 p-4 font-sans text-lg leading-8 font-light tracking-normal whitespace-pre-wrap wrap-anywhere text-transparent"
          >
            {parts.map((part, index) => (
              <Fragment key={part.start}>
                {text.slice(index ? parts[index - 1].end : 0, part.start)}
                <mark
                  data-field={part.label}
                  className={cn(
                    highlightClass,
                    "text-transparent",
                    fieldColors[part.label]?.highlight,
                  )}
                >
                  {text.slice(part.start, part.end)}
                </mark>
              </Fragment>
            ))}
            {text.slice(parts.at(-1)?.end ?? 0)}
            {"\u200b"}
          </div>
          <Textarea
            id="address"
            value={text}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={!!error}
            aria-describedby={
              error ? "address-guidance parser-error" : "address-guidance"
            }
            className="absolute inset-0 field-sizing-fixed h-full min-h-0 w-full resize-none rounded-none border-0 bg-transparent p-4 font-sans text-lg leading-8 font-light tracking-normal whitespace-pre-wrap wrap-anywhere shadow-none focus-visible:ring-0 md:text-lg dark:bg-transparent"
            placeholder="Paste a full address…"
            onChange={(event) => edit(event.target.value)}
            onCompositionStart={() => {
              sequence.current++;
              setComposing(true);
            }}
            onCompositionEnd={() => setComposing(false)}
          />
        </div>
      </Field>
      <div
        className="mt-3 flex min-h-5 flex-wrap gap-x-4 gap-y-2"
        aria-label="Address field colors"
      >
        {fields.map((field) => (
          <span
            key={field}
            className={cn(
              "inline-flex items-center gap-1.5 text-xs",
              fieldColors[field]?.text,
            )}
          >
            <span
              aria-hidden="true"
              className="size-1.5 bg-[repeating-conic-gradient(currentColor_0_25%,transparent_0_50%)] bg-size-[2px_2px]"
            />
            {names[field] || field}
          </span>
        ))}
      </div>
      <div className="sr-only" role="status">
        {busy
          ? "Parsing address"
          : parts.length
            ? parts
                .map(
                  (part) => `${names[part.label] || part.label}: ${part.raw}`,
                )
                .join(". ")
            : text.trim() && ready
              ? "No address fields identified."
              : "Enter an address."}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2" aria-label="Example addresses">
        {samples.map(({ label, address, parts: exampleParts }) => (
          <Button
            key={label}
            className="h-auto min-w-0 flex-col items-start justify-start gap-1 border border-dotted border-border px-3 py-3 text-left font-normal whitespace-normal"
            variant="ghost"
            disabled={!ready}
            aria-label={`Try ${label} address`}
            onClick={() => edit(address)}
          >
            <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <Image
                src={`/logos/${label.toLowerCase()}.svg`}
                alt=""
                width={16}
                height={16}
                className="size-4 shrink-0 object-contain opacity-80 brightness-0 invert"
              />
              {label}
            </span>
            <span className="text-sm leading-6">
              {exampleParts.map((part, index) => (
                <Fragment key={sampleFields[index]}>
                  {index > 0 && " "}
                  <mark
                    data-field={sampleFields[index]}
                    className={cn(
                      highlightClass,
                      "text-foreground",
                      fieldColors[sampleFields[index]].highlight,
                    )}
                  >
                    {part}
                  </mark>
                </Fragment>
              ))}
            </span>
          </Button>
        ))}
      </div>
      {error && (
        <Alert id="parser-error" variant="destructive" className="mt-4">
          <AlertTitle>Parser notice</AlertTitle>
          <AlertDescription>
            {error}
            {!ready &&
              " Use a WebGPU browser over HTTPS or localhost, then reload."}
          </AlertDescription>
        </Alert>
      )}
    </section>
  );
}
