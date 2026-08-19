import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Provenance } from "@/components/provenance";
import { SiteNav } from "@/components/site-nav";
import { getManifest } from "@/lib/data";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-face",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FPL V1 — research viewer",
  description:
    "Projection-first Fantasy Premier League research viewer. Frozen predictions, evaluation metrics, and calibration evidence.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const manifest = await getManifest();

  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen font-sans antialiased">
        <div className="mx-auto flex min-h-screen max-w-[1400px] flex-col px-5 lg:px-8">
          <SiteNav manifest={manifest} />
          <main className="flex-1 pb-16">{children}</main>
          <Provenance manifest={manifest} />
        </div>
      </body>
    </html>
  );
}
