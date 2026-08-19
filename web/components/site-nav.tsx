"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

import type { Manifest } from "@/lib/types";
import { seasonLabel } from "@/lib/format";

export function SiteNav({ manifest }: { manifest: Manifest }) {
  const pathname = usePathname();
  const labSeasons = manifest.seasons.filter((s) => s.has_lab).map((s) => s.season);
  const latest = labSeasons.at(-1) ?? manifest.live_season;

  const links = [
    { href: "/", label: "Pool", match: (p: string) => p === "/" },
    {
      href: `/squad/${latest}/1`,
      label: "XI board",
      match: (p: string) => p.startsWith("/squad"),
    },
    { href: `/lab/${latest}`, label: "Lab", match: (p: string) => p.startsWith("/lab") },
    { href: "/audit", label: "Audit", match: (p: string) => p.startsWith("/audit") },
  ];

  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-3 py-6">
      <Link href="/" className="group flex items-baseline gap-2">
        <span className="text-[15px] font-semibold tracking-tight">FPL</span>
        <span className="rounded bg-model/12 px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-wider text-model">
          V1
        </span>
      </Link>

      <nav className="flex items-center gap-1">
        {links.map((link) => {
          const active = link.match(pathname);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={clsx(
                "rounded-md px-2.5 py-1.5 text-[13px] transition-colors",
                active
                  ? "bg-raised text-ink"
                  : "text-muted hover:bg-raised/60 hover:text-ink",
              )}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <span className="label-xs">Research viewer</span>
        <span
          className="rounded border border-edge px-1.5 py-0.5 font-mono text-[10px] text-muted"
          title="Latest season with a full evaluation panel"
        >
          {seasonLabel(latest)}
        </span>
      </div>
    </header>
  );
}
