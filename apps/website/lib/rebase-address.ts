import type { ParseResult } from "gpu-postal";

// Keep highlights attached to unchanged text while the next parse is pending.
export function rebaseAddress(
  result: ParseResult | null,
  previous: string,
  next: string,
): ParseResult | null {
  if (!result || !next.trim()) return null;
  let start = 0;
  while (
    start < previous.length &&
    start < next.length &&
    previous[start] === next[start]
  )
    start++;
  let end = previous.length;
  let nextEnd = next.length;
  while (
    end > start &&
    nextEnd > start &&
    previous[end - 1] === next[nextEnd - 1]
  ) {
    end--;
    nextEnd--;
  }
  const delta = next.length - previous.length;
  return {
    ...result,
    components: result.components.flatMap((part) => {
      let from = part.start;
      let to = part.end;
      if (to <= start) {
        // Before the edit.
      } else if (from >= end) {
        from += delta;
        to += delta;
      } else if (from <= start && to >= end && (start > from || end < to)) {
        to += delta;
      } else {
        return [];
      }
      return to > from
        ? [{ ...part, start: from, end: to, raw: next.slice(from, to) }]
        : [];
    }),
  };
}
