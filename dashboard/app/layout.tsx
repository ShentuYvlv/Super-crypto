import "./globals.css";

import type { ReactNode } from "react";
import type { Metadata } from "next";

import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Super Crypto Dashboard",
  description: "Read-only quant research terminal"
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
