"use client";

import Link from "next/link";
import clsx from "clsx";

import type { DecisionGw } from "@/lib/types";

/**
 * Gameweek picker that doubles as an evaluation-status strip. Flagged weeks are
 * structurally tagged and never set from model scores.
 */
export function GwStrip({
  season,
  current,
  gws,
  decisions,
  basePath = "squad",
}: {
  season: string;
  current: number;
  gws: number[];
  decisions: DecisionGw[];
  basePath?: string;
}) {
  const statusOf = new Map(decisions.map((d) => [d.gw, d.status]));

  return (
    <div className="flex flex-nowrap gap-0.5 overflow-x-auto pb-0.5">
      {gws.map((gw) => {
        const status = statusOf.get(gw);
        const active = gw === current;
        return (
          <Link
            key={gw}
            href={`/${basePath}/${season}/${gw}`}
            title={status ? `GW${gw} — ${status}` : `GW${gw}`}
            className={clsx(
              "tnum relative w-7 shrink-0 rounded border py-0.5 text-center text-[10px] transition-colors",
              active
                ? "border-model bg-model/15 text-model"
                : "border-edge text-muted hover:border-edge-bright hover:text-ink",
            )}
          >
            {gw}
            {status === "flagged" && (
              <span
                className="absolute top-0.5 right-0.5 h-1 w-1 rounded-full bg-b0"
                aria-hidden
              />
            )}
          </Link>
        );
      })}
    </div>
  );
}

export function SeasonTabs({
  seasons,
  current,
  basePath,
}: {
  seasons: string[];
  current: string;
  basePath: string;
}) {
  return (
    <div className="flex gap-1">
      {seasons.map((season) => (
        <Link
          key={season}
          href={basePath === "lab" ? `/lab/${season}` : `/${basePath}/${season}/1`}
          className={clsx(
            "rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors",
            season === current
              ? "bg-raised text-ink"
              : "text-muted hover:bg-raised/60 hover:text-ink",
          )}
        >
          {season.replace("-", "/")}
        </Link>
      ))}
    </div>
  );
}
