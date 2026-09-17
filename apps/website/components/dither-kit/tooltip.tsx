"use client";

import {
  autoUpdate,
  flip,
  offset,
  shift,
  useFloating,
} from "@floating-ui/react-dom";
import { useLayoutEffect } from "react";
import { createPortal } from "react-dom";
import { useCommonChart } from "./common-context";
import { cn } from "./lib";
import { rgb } from "./palette";

export type TooltipVariant = "default" | "frosted-glass";

const VARIANT: Record<TooltipVariant, string> = {
  default: "bg-popover",
  "frosted-glass": "bg-popover/70 backdrop-blur-sm",
};

/** Viewport-aware tooltip shared by every chart family. */
export function Tooltip({
  labelKey,
  valueFormatter,
  variant = "default",
}: {
  labelKey?: string;
  valueFormatter?: (value: number, name: string) => string;
  variant?: TooltipVariant;
}) {
  const chart = useCommonChart();
  const show = chart.ready && chart.hoverIndex != null;

  const { refs, floatingStyles, update } = useFloating({
    placement: "top",
    strategy: "fixed",
    middleware: [offset(8), flip({ padding: 8 }), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  });
  useLayoutEffect(() => {
    update();
  }, [chart.tooltipLeft, chart.tooltipTop, update]);

  const index = chart.hoverIndex ?? 0;

  const heading = chart.heading(index, labelKey);
  const items = chart.itemsAt(index);

  return (
    <>
      <span
        ref={refs.setReference}
        aria-hidden
        className="pointer-events-none absolute size-0"
        style={{ top: chart.tooltipTop, left: chart.tooltipLeft }}
      />
      {show &&
        items.length > 0 &&
        createPortal(
          <div
            ref={refs.setFloating}
            role="tooltip"
            style={floatingStyles}
            className={cn(
              "pointer-events-none z-50 w-max max-w-[calc(100vw-1rem)] rounded-md border border-border px-3 py-2 shadow-sm",
              VARIANT[variant],
            )}
          >
            {heading && (
              <div className="mb-0.5 text-[10px] text-muted-foreground">
                {heading}
              </div>
            )}
            <div className="flex flex-col gap-0.5">
              {items.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center gap-1.5 text-[11px] text-popover-foreground tabular-nums data-[dimmed=true]:opacity-40"
                  data-dimmed={item.dimmed}
                >
                  <span
                    className="size-2 shrink-0 rounded-[1px]"
                    style={{ backgroundColor: rgb(item.seed.fill) }}
                  />
                  <span className="min-w-0 text-muted-foreground">
                    {item.label}
                  </span>
                  <span className="ml-auto shrink-0 pl-2 text-foreground">
                    {valueFormatter
                      ? valueFormatter(item.value, item.name)
                      : item.value.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}

Tooltip.chartLayer = "dom" as const;
