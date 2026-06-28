"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "Overview" },
  { href: "/experiments", label: "Experiments" },
  { href: "/backtest", label: "Backtest" },
  { href: "/signals", label: "Signals" },
  { href: "/trades", label: "Trades" },
  { href: "/symbols", label: "Symbols" },
  { href: "/data-quality", label: "Data Quality" },
  { href: "/orderbook", label: "Orderbook" },
  { href: "/reports", label: "Reports" }
];

export function SideNav() {
  const pathname = usePathname();
  return (
    <aside className="flex w-full flex-col border-b border-border bg-[#0e1218] px-4 py-6 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-accent">Super Crypto</h1>
        <p className="text-sm text-muted">Quant Research Terminal</p>
      </div>
      <nav className="grid gap-2 md:grid-cols-3 lg:grid-cols-1">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-3 text-sm text-muted transition hover:bg-surface2 hover:text-text",
                active && "bg-surface2 text-text"
              )}
            >
              <span className={cn("h-2 w-2 rounded-full bg-muted", active && "bg-accent")} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto rounded-lg border border-border bg-surface p-4">
        <p className="text-sm font-semibold text-accent">Holdout Guard</p>
        <p className="mt-2 text-sm text-muted">
          Final holdout is read-only. No run action exists in dashboard.
        </p>
      </div>
    </aside>
  );
}
