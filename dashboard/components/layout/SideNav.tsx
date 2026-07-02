"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "总览" },
  { href: "/experiments", label: "实验", activePaths: ["/backtest"] },
  { href: "/phase1", label: "预测实验" },
  { href: "/cycles", label: "操盘周期" },
  { href: "/autoresearch", label: "研究循环" },
  { href: "/signals", label: "信号" },
  { href: "/symbols", label: "数据", activePaths: ["/data-quality"] },
  { href: "/reports", label: "报告" }
];

export function SideNav() {
  const pathname = usePathname();
  const normalizedPathname =
    pathname !== "/" && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return (
    <aside className="flex w-full flex-col border-b border-border bg-[#0e1218] px-4 py-6 lg:sticky lg:top-0 lg:min-h-screen lg:w-64 lg:self-start lg:border-b-0 lg:border-r">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-accent">Super Crypto</h1>
        <p className="text-sm text-muted">量化研究终端</p>
      </div>
      <nav className="grid gap-2 md:grid-cols-3 lg:grid-cols-1">
        {items.map((item) => {
          const activePaths = [item.href, ...(item.activePaths ?? [])];
          const active =
            item.href === "/"
              ? normalizedPathname === "/"
              : activePaths.some(
                  (activePath) =>
                    normalizedPathname === activePath ||
                    normalizedPathname.startsWith(`${activePath}/`)
                );
          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch={false}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex items-center gap-3 overflow-hidden rounded-md border border-transparent px-3 py-3 text-sm text-muted transition hover:bg-surface2 hover:text-text",
                active &&
                  "border-accent/40 bg-surface2 pl-4 font-semibold text-text shadow-panel"
              )}
            >
              <span
                className={cn(
                  "absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-transparent transition",
                  active && "bg-accent"
                )}
              />
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full bg-muted transition group-hover:bg-text",
                  active && "bg-accent shadow-[0_0_14px_rgba(252,213,53,.65)]"
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto rounded-lg border border-border bg-surface p-4">
        <p className="text-sm font-semibold text-accent">留出集保护</p>
        <p className="mt-2 text-sm text-muted">
          最终留出集只读；看板不提供执行入口。
        </p>
      </div>
    </aside>
  );
}
