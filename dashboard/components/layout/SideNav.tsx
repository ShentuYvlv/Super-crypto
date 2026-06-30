"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/", label: "总览" },
  { href: "/experiments", label: "实验" },
  { href: "/autoresearch", label: "研究循环" },
  { href: "/backtest", label: "回测" },
  { href: "/signals", label: "信号" },
  { href: "/trades", label: "交易" },
  { href: "/symbols", label: "标的" },
  { href: "/data-quality", label: "数据质量" },
  { href: "/orderbook", label: "盘口" },
  { href: "/reports", label: "报告" }
];

export function SideNav() {
  const pathname = usePathname();
  return (
    <aside className="flex w-full flex-col border-b border-border bg-[#0e1218] px-4 py-6 lg:sticky lg:top-0 lg:min-h-screen lg:w-64 lg:self-start lg:border-b-0 lg:border-r">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-accent">Super Crypto</h1>
        <p className="text-sm text-muted">量化研究终端</p>
      </div>
      <nav className="grid gap-2 md:grid-cols-3 lg:grid-cols-1">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch={false}
              className={cn(
                "flex items-center gap-3 rounded-md border border-transparent px-3 py-3 text-sm text-muted transition hover:bg-surface2 hover:text-text",
                active && "border-accent/30 bg-surface2 text-text shadow-panel"
              )}
            >
              <span className={cn("h-2 w-2 rounded-full bg-muted", active && "bg-accent")} />
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
