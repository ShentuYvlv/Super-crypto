import "./globals.css";

import type { ReactNode } from "react";
import type { Metadata } from "next";

import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Super Crypto 研究看板",
  description: "只读量化研究终端"
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
