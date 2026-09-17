"use client";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
export function CopyButton({ text, label }: { text: string; label: string }) {
  const [message, setMessage] = useState("");
  return (
    <span className="relative inline-flex shrink-0">
      <Button
        variant="ghost"
        size="icon"
        aria-label={label}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            setMessage("Copied");
          } catch {
            setMessage("Copy unavailable. Select the text to copy.");
          }
        }}
      >
        {message === "Copied" ? <Check /> : <Copy />}
      </Button>
      <span
        role="status"
        className="absolute right-0 bottom-full w-max max-w-45 bg-card text-[10px] leading-normal text-primary not-empty:border not-empty:border-border not-empty:px-2 not-empty:py-1.25"
      >
        {message}
      </span>
    </span>
  );
}
