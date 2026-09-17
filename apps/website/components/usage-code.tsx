"use client";

import { useEffect, useState } from "react";
import type { parse } from "gpu-lexer";

type Highlighted = { source: string; spans: Awaited<ReturnType<typeof parse>> };

export function UsageCode({ code }: { code: string }) {
  const [highlighted, setHighlighted] = useState<Highlighted | null>(null);

  useEffect(() => {
    let cancelled = false;
    import("gpu-lexer")
      .then(({ parse }) => parse(code))
      .then((spans) => {
        if (!cancelled) setHighlighted({ source: code, spans });
      })
      .catch(() => {
        // Keep the server-rendered source readable when WebGPU is unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  return (
    <pre
      data-slot="usage-code"
      className="overflow-auto p-4 font-mono text-xs leading-relaxed text-muted-foreground sm:p-5"
    >
      <code>
        {highlighted?.source === code
          ? highlighted.spans.map(({ type, start, end }) => (
              <span
                key={start}
                data-syntax={type}
                className="data-[syntax=keyword]:font-medium data-[syntax=keyword]:text-foreground data-[syntax=type]:font-medium data-[syntax=type]:text-foreground data-[syntax=constant]:font-medium data-[syntax=constant]:text-foreground data-[syntax=string]:text-primary data-[syntax=number]:text-primary data-[syntax=function]:text-foreground data-[syntax=comment]:italic"
              >
                {code.slice(start, end)}
              </span>
            ))
          : code}
      </code>
    </pre>
  );
}
