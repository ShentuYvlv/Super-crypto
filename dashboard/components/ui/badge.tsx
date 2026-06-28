import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const toneMap = {
  neutral: "border-border text-text",
  accent: "border-accent/40 bg-accent/10 text-accent",
  positive: "border-positive/40 bg-positive/10 text-positive",
  negative: "border-negative/40 bg-negative/10 text-negative",
  warning: "border-warning/40 bg-warning/10 text-warning",
  info: "border-info/40 bg-info/10 text-info"
} as const;

export function Badge({
  children,
  tone = "neutral",
  className
}: {
  children: ReactNode;
  tone?: keyof typeof toneMap;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-medium",
        toneMap[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
