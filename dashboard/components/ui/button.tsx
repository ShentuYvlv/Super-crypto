import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Button({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-md bg-accent px-3 py-2 text-sm font-semibold text-black transition hover:bg-accentHover",
        className
      )}
    >
      {children}
    </button>
  );
}
