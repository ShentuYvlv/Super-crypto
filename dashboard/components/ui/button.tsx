import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Button({
  children,
  className,
  ...props
}: {
  children: ReactNode;
  className?: string;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        "rounded-md bg-accent px-3 py-2 text-sm font-semibold text-black transition hover:bg-accentHover",
        className
      )}
    >
      {children}
    </button>
  );
}
