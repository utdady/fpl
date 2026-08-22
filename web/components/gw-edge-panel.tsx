"use client";

import clsx from "clsx";

import { dec } from "@/lib/format";
import type { GwEdgeExtended } from "@/lib/team-compare";

/** Collapsible GW win-chance bar + expanded stats. */
export function GwEdgePanel({
  edge,
  mineLabel = "You",
  rivalLabel = "Them",
  compact = false,
}: {
  edge: GwEdgeExtended;
  mineLabel?: string;
  rivalLabel?: string;
  compact?: boolean;
}) {
  const pYou = edge.pMineAhead;
  const pThem = pYou != null ? 1 - pYou : null;
  const youPct = pYou != null ? Math.round(pYou * 100) : null;
  const themPct = pThem != null ? Math.round(pThem * 100) : null;

  return (
    <details
      className={clsx(
        "group rounded-md border border-edge bg-raised/30",
        compact && "text-[11px]",
      )}
    >
      <summary className="cursor-pointer list-none px-3 py-2.5 marker:content-none [&::-webkit-details-marker]:hidden">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="label-xs shrink-0 text-ink">GW edge</span>
          {youPct != null && themPct != null ? (
            <>
              <EdgeBar youPct={youPct} themPct={themPct} className="min-w-[140px] flex-1" />
              <span className="tnum shrink-0 text-[11px] text-muted">
                {mineLabel}{" "}
                <span className="font-medium text-model">{youPct}%</span>
                {" · "}
                {rivalLabel}{" "}
                <span className="font-medium text-ink">{themPct}%</span>
              </span>
            </>
          ) : (
            <span className="tnum text-[11px] text-muted">
              μ gap {edge.d >= 0 ? "+" : ""}
              {dec(edge.d, 1)} (σ unavailable)
            </span>
          )}
        </div>
      </summary>

      <div className="space-y-2 border-t border-edge px-3 py-3 text-[12px]">
        {youPct != null ? (
          <p className="tnum text-ink">
            P({mineLabel.toLowerCase()} score more this GW) ≈{" "}
            <span className="text-model">{youPct}%</span>
            {edge.sigmaD != null && (
              <span className="ml-2 text-[11px] text-faint">
                μ gap {dec(edge.d, 1)} · σ_D {dec(edge.sigmaD, 1)}
              </span>
            )}
          </p>
        ) : (
          <p className="text-muted">
            Gap only (missing σ on unplayed slots):{" "}
            <span className="tnum text-ink">
              {edge.d >= 0 ? "+" : ""}
              {dec(edge.d, 1)}
            </span>
          </p>
        )}

        <p className="tnum text-muted">
          XI+C total: {rivalLabel}{" "}
          <span className="text-model">{dec(edge.rivalDisplay.mu, 1)}</span>
          {edge.rivalDisplay.sigma != null && edge.rivalDisplay.sigma > 0 ? (
            <span className="text-faint"> ± {dec(edge.rivalDisplay.sigma, 1)}</span>
          ) : null}
          {" · "}
          {mineLabel}{" "}
          <span className="text-model">{dec(edge.mineDisplay.mu, 1)}</span>
          {edge.mineDisplay.sigma != null && edge.mineDisplay.sigma > 0 ? (
            <span className="text-faint"> ± {dec(edge.mineDisplay.sigma, 1)}</span>
          ) : null}
        </p>

        {edge.live && (
          <p className="tnum text-[11px] text-muted">
            Locked: {rivalLabel}{" "}
            <span className="text-actual">{edge.rivalBreakdown.locked}</span>
            {" · "}
            {mineLabel} <span className="text-actual">{edge.mineBreakdown.locked}</span>
            {" · "}
            Still projected: {rivalLabel}{" "}
            <span className="text-model">{dec(edge.rivalBreakdown.projectedMu, 1)}</span>
            {" · "}
            {mineLabel}{" "}
            <span className="text-model">{dec(edge.mineBreakdown.projectedMu, 1)}</span>
          </p>
        )}

        <p className="text-[11px] leading-relaxed text-faint">
          {edge.live
            ? "Played XI slots use in-play FPL points; unplayed slots use frozen V1 μ/σ. Updates during the gameweek."
            : "Independent Normal on XI+C totals from the frozen pool — not live FPL xP, not season title odds."}{" "}
          Captain contributes 2× on points / μ and 4× on σ² for projected slots.
        </p>
      </div>
    </details>
  );
}

function EdgeBar({
  youPct,
  themPct,
  className,
}: {
  youPct: number;
  themPct: number;
  className?: string;
}) {
  return (
    <div className={clsx("flex h-2 overflow-hidden rounded-full bg-raised", className)}>
      <div
        className="bg-muted/80 transition-[width] duration-500"
        style={{ width: `${themPct}%` }}
        title={`Them ${themPct}%`}
      />
      <div
        className="bg-model/70 transition-[width] duration-500"
        style={{ width: `${youPct}%` }}
        title={`You ${youPct}%`}
      />
    </div>
  );
}

/** Inline bar only — for team list rows. */
export function GwEdgeBar({
  edge,
  mineLabel = "You",
  rivalLabel = "Them",
}: {
  edge: GwEdgeExtended;
  mineLabel?: string;
  rivalLabel?: string;
}) {
  if (edge.pMineAhead == null) return null;
  const youPct = Math.round(edge.pMineAhead * 100);
  const themPct = 100 - youPct;
  return (
    <div className="flex min-w-[120px] max-w-[200px] flex-col gap-0.5">
      <EdgeBar youPct={youPct} themPct={themPct} />
      <span className="tnum text-[10px] text-faint">
        {mineLabel} {youPct}% · {rivalLabel} {themPct}%
      </span>
    </div>
  );
}
