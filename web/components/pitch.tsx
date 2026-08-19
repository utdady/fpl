"use client";

import { useState } from "react";

import { PlayerCell, isBlank, type CellPlayer } from "./player-cell";
import { PlayerDrawer } from "./player-drawer";
import { POSITIONS } from "@/lib/format";
import type { Position } from "@/lib/types";

/**
 * Renders an eleven, not a fifteen. decision_decomp.csv holds the XI only, so
 * there is no bench to draw.
 */
export function Pitch({
  players,
  season,
  gw,
  bench = [],
}: {
  players: CellPlayer[];
  season: string;
  gw: number;
  bench?: CellPlayer[];
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const rows = POSITIONS.map((pos) => players.filter((p) => p.pos === pos)).filter(
    (row) => row.length > 0,
  );

  const roster = [...players, ...bench];
  const active = roster.find((p) => p.id === selected) ?? null;

  return (
    <>
      <div className="relative overflow-hidden rounded-xl border border-edge">
        <PitchMarkings />
        <div className="relative flex flex-col gap-5 px-4 py-7">
          {rows.map((row, i) => (
            <div key={i} className="flex flex-wrap justify-center gap-2.5">
              {row.map((player) => (
                <PlayerCell key={player.id} player={player} onSelect={setSelected} />
              ))}
            </div>
          ))}
        </div>
      </div>

      {bench.length > 0 && (
        <div className="mt-3">
          <div className="label-xs mb-2">Bench</div>
          <div className="flex flex-wrap gap-2">
            {bench.map((player) => (
              <PlayerCell key={player.id} player={player} compact onSelect={setSelected} />
            ))}
          </div>
        </div>
      )}

      <PlayerDrawer
        player={active}
        season={season}
        gw={gw}
        onClose={() => setSelected(null)}
      />
    </>
  );
}

function PitchMarkings() {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      aria-hidden
      style={{
        background:
          "linear-gradient(180deg, color-mix(in oklab, var(--color-plum) 40%, transparent), color-mix(in oklab, var(--color-void) 92%, transparent))",
      }}
    >
      <svg className="h-full w-full opacity-[0.13]" preserveAspectRatio="none" viewBox="0 0 100 120">
        <rect x="1" y="1" width="98" height="118" fill="none" stroke="currentColor" strokeWidth="0.4" />
        <line x1="1" y1="60" x2="99" y2="60" stroke="currentColor" strokeWidth="0.4" />
        <circle cx="50" cy="60" r="12" fill="none" stroke="currentColor" strokeWidth="0.4" />
        <rect x="28" y="1" width="44" height="16" fill="none" stroke="currentColor" strokeWidth="0.4" />
        <rect x="28" y="103" width="44" height="16" fill="none" stroke="currentColor" strokeWidth="0.4" />
      </svg>
    </div>
  );
}

/** Compact list form, used beside the pitch to compare the two elevens. */
export function XiList({
  players,
  title,
  tone,
}: {
  players: CellPlayer[];
  title: string;
  tone: "model" | "b0";
}) {
  const total = players.reduce((sum, p) => sum + (p.pts ?? 0), 0);
  const blanks = players.filter(isBlank).length;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="label-xs">{title}</span>
        <span className="tnum text-[11px] text-muted">
          {total} pts{blanks > 0 && <span className="ml-1.5 text-risk">{blanks} blank</span>}
        </span>
      </div>
      <ul className="mt-2 space-y-px">
        {players.map((p) => (
          <li
            key={p.id}
            className="flex items-baseline justify-between gap-2 rounded px-1.5 py-1 text-[11.5px] odd:bg-raised/40"
          >
            <span className="truncate text-ink">
              {p.name}
              {p.captain && (
                <span className={`ml-1 text-${tone} text-[9px] font-bold`}>C</span>
              )}
            </span>
            <span className="tnum shrink-0 text-faint">
              <span className={isBlank(p) ? "text-risk" : "text-actual"}>{p.pts ?? "—"}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export type { Position };
