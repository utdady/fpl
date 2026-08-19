"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";

import { PlayerDrawer } from "./player-drawer";
import { PlayerHover } from "./player-hover";
import { POSITIONS, calibratedStart, dec, difficultyColor, pct, price } from "@/lib/format";
import { useLive, type LiveStat } from "@/lib/use-live";
import type { Position } from "@/lib/types";
import type { CellPlayer } from "./player-cell";

export type PoolRow = {
  id: number;
  name: string;
  pos: Position;
  teamCode: string | null;
  cost: number | null;
  mu: number | null;
  sigma: number | null;
  pStart: number | null;
  p60: number | null;
  p10: number | null;
  pts: number | null;
  mins: number | null;
  chanceNext: number | null;
  owned: number | null;
  epNext: number | null;
  status: string | null;
  news: string | null;
  opponent: string | null;
  home: boolean | null;
  fdr: number | null;
};

type SortKey = "mu" | "cost" | "pStart" | "p10" | "owned" | "epNext";

const COLUMNS: { key: SortKey; label: string; tone?: string }[] = [
  { key: "cost", label: "Price" },
  { key: "mu", label: "xP", tone: "text-model" },
  { key: "pStart", label: "P(start)" },
  { key: "p10", label: "P(10+)" },
  { key: "epNext", label: "FPL ep" },
  { key: "owned", label: "Owned" },
];

export function PoolTable({
  rows,
  season,
  gw,
}: {
  rows: PoolRow[];
  season: string;
  gw: number;
}) {
  const [sort, setSort] = useState<SortKey>("mu");
  const [position, setPosition] = useState<Position | "ALL">("ALL");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [limit, setLimit] = useState(60);
  const [liveOn, setLiveOn] = useState(false);
  const live = useLive(gw, liveOn);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows
      .filter((r) => (position === "ALL" ? true : r.pos === position))
      .filter((r) => (needle ? r.name.toLowerCase().includes(needle) : true))
      .sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
  }, [rows, sort, position, query]);

  const active = rows.find((r) => r.id === selected) ?? null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          {(["ALL", ...POSITIONS] as const).map((pos) => (
            <button
              key={pos}
              type="button"
              onClick={() => setPosition(pos)}
              className={clsx(
                "rounded px-2 py-1 text-[11px] transition-colors",
                position === pos
                  ? "bg-raised text-ink"
                  : "text-muted hover:bg-raised/60 hover:text-ink",
              )}
            >
              {pos}
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search player"
          className="ml-auto w-44 rounded-md border border-edge bg-void/60 px-2.5 py-1.5 text-[12px] outline-none placeholder:text-faint focus:border-edge-bright"
        />
        <LiveToggle on={liveOn} onChange={setLiveOn} status={live.status} at={live.fetchedAt} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-[12px]">
          <thead>
            <tr className="border-b border-edge">
              <th className="label-xs py-2 pr-3 text-left font-normal">Player</th>
              <th className="label-xs py-2 pr-3 text-left font-normal">Fixture</th>
              {COLUMNS.map((col) => (
                <th key={col.key} className="py-2 pr-3 text-right font-normal">
                  <button
                    type="button"
                    onClick={() => setSort(col.key)}
                    className={clsx(
                      "label-xs transition-colors hover:text-ink",
                      sort === col.key && "text-ink",
                    )}
                  >
                    {col.label}
                    {sort === col.key && <span className="ml-0.5">↓</span>}
                  </button>
                </th>
              ))}
              {liveOn && <th className="label-xs py-2 text-right font-normal">Live</th>}
            </tr>
          </thead>
          <tbody>
            {visible.slice(0, limit).map((row) => (
              <Row
                key={row.id}
                row={row}
                onSelect={setSelected}
                live={liveOn ? (live.stats.get(row.id) ?? null) : undefined}
              />
            ))}
          </tbody>
        </table>
      </div>

      {visible.length > limit && (
        <button
          type="button"
          onClick={() => setLimit(limit + 100)}
          className="mt-3 w-full rounded-md border border-edge py-2 text-[11.5px] text-muted transition-colors hover:border-edge-bright hover:text-ink"
        >
          Show more ({visible.length - limit} remaining)
        </button>
      )}

      <PlayerDrawer
        player={active ? toCell(active) : null}
        season={season}
        gw={gw}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function LiveToggle({
  on,
  onChange,
  status,
  at,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  status: ReturnType<typeof useLive>["status"];
  at: Date | null;
}) {
  const label =
    status === "loading"
      ? "connecting"
      : status === "error"
        ? "unavailable"
        : status === "ready" && at
          ? at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "off";

  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      title="Fetches in-play points through the server proxy, refreshed every 60 seconds"
      className={clsx(
        "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] transition-colors",
        on
          ? status === "error"
            ? "border-risk/50 text-risk"
            : "border-actual/50 text-actual"
          : "border-edge text-muted hover:border-edge-bright hover:text-ink",
      )}
    >
      <span
        className={clsx(
          "h-1.5 w-1.5 rounded-full",
          on && status === "ready" && "animate-pulse bg-actual",
          on && status === "loading" && "animate-pulse bg-muted",
          on && status === "error" && "bg-risk",
          !on && "bg-faint",
        )}
      />
      Live
      <span className="tnum text-faint">{label}</span>
    </button>
  );
}

function Row({
  row,
  onSelect,
  live,
}: {
  row: PoolRow;
  onSelect: (id: number) => void;
  live?: LiveStat | null;
}) {
  const observed = calibratedStart(row.pStart);
  const overconfident = row.pStart != null && observed != null && row.pStart - observed > 0.08;

  return (
    <tr
      onClick={() => onSelect(row.id)}
      className="cursor-pointer border-b border-edge/40 transition-colors hover:bg-raised/50"
    >
      <td className="py-1.5 pr-3">
        <PlayerHover player={toCell(row)}>
          <span className="flex items-center gap-2">
            <span className="label-xs w-8 shrink-0">{row.teamCode ?? "—"}</span>
            <span className="truncate font-medium text-ink">{row.name}</span>
            {row.news && (
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-risk"
                title={row.news}
                aria-label="Injury or availability news"
              />
            )}
          </span>
        </PlayerHover>
      </td>
      <td className="py-1.5 pr-3">
        {row.opponent ? (
          <span className="tnum flex items-center gap-1.5 text-[11px] text-muted">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: difficultyColor(row.fdr) }}
              title={`Difficulty ${row.fdr}`}
            />
            {row.opponent}
            <span className="text-faint">{row.home ? "H" : "A"}</span>
          </span>
        ) : (
          <span className="text-faint">—</span>
        )}
      </td>
      <td className="tnum py-1.5 pr-3 text-right text-muted">{price(row.cost)}</td>
      <td className="tnum py-1.5 pr-3 text-right font-semibold text-model">
        {dec(row.mu, 2)}
      </td>
      <td className="tnum py-1.5 pr-3 text-right">
        <span className={overconfident ? "text-risk" : "text-muted"}>
          {pct(row.pStart, 0)}
        </span>
      </td>
      <td className="tnum py-1.5 pr-3 text-right text-muted">{pct(row.p10, 1)}</td>
      <td className="tnum py-1.5 pr-3 text-right text-b0">{dec(row.epNext, 1)}</td>
      <td className="tnum py-1.5 pr-3 text-right text-faint">
        {row.owned == null ? "—" : `${row.owned}%`}
      </td>
      {live !== undefined && (
        <td className="tnum py-1.5 text-right">
          {live == null ? (
            <span className="text-faint">—</span>
          ) : (
            <span className={live.minutes === 0 ? "text-risk" : "text-actual"}>
              {live.points}
              <span className="ml-1 text-[10px] text-faint">{live.minutes}&apos;</span>
            </span>
          )}
        </td>
      )}
    </tr>
  );
}

function toCell(row: PoolRow): CellPlayer {
  return {
    id: row.id,
    name: row.name,
    pos: row.pos,
    cost: row.cost,
    teamCode: row.teamCode,
    mu: row.mu,
    sigma: row.sigma,
    pStart: row.pStart,
    p10: row.p10,
    pts: row.pts,
    mins: row.mins,
    chanceNext: row.chanceNext,
    owned: row.owned,
    epNext: row.epNext,
    status: row.status,
    news: row.news,
  };
}
