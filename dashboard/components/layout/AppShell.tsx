"use client";

import type { ReactNode } from "react";

import { SideNav } from "@/components/layout/SideNav";
import { TopStatusBar } from "@/components/layout/TopStatusBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-text lg:flex-row">
      <SideNav />
      <main className="min-w-0 flex-1 px-6 py-6">
        <TopStatusBar />
        {children}
      </main>
    </div>
  );
}
