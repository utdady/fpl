"use client";

import { useEffect, useMemo, useState } from "react";

import { Section } from "./ui/section";
import { dec, price } from "@/lib/format";
import type { Position, StrategyKey } from "@/lib/types";

const STORAGE = "fpl.tracked-entries";

export type PoolPlayer = {
  id: number;
  name: string;
  pos: Position;
  teamCode: string | null;
  cost: number | null;
  mu: number | null;
  pStart: number | null;
};

type Entry = {
  id: number;
  name: string;
  player_first_name?: string;
  player_last_name?: string;
  summary_overall_points?: number;
  summary_overall_rank?: number;
  last_deadline_bank?: number;
  current_event?: number;
};

type Pick = {
  element: number;
  position: number;
  is_captain: boolean;
  is_vice_captain: boolean;
};

type HistoryRow = {
  event: number;
  points: number;
  total_points: number;
  rank: number | null;
  event_transfers: number;
  event_transfers_cost: number;
  bank: number;
  value: number;
};

function loadIds(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE);
    const parsed = raw ? (JSON.parse(raw) as number[]) : [];
    return parsed.filter((n) => Number.isInteger(n) && n > 0);
  } catch {
    return [];
  }
}

async function fpl<T>(path: string): Promise<{ ok: true; data: T } | { ok: false; status: number }> {
  const response = await fetch(`/api/fpl/${path}`);
  if (!response.ok) return { ok: false, status: response.status };
  return { ok: true, data: (await response.json()) as T };
}

export function TeamTracker({
  gw,
  pool,
  balancedIds,
}: {
  gw: number;
  pool: PoolPlayer[];
  balancedIds: number[];
  strategy: StrategyKey;
}) {
  const [ids, setIds] = useState<number[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setIds(loadIds());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (ids.length) localStorage.setItem(STORAGE, JSON.stringify(ids));
    else localStorage.removeItem(STORAGE);
  }, [ids, ready]);

  function add() {
    const id = Number(draft.trim());
    if (!Number.isInteger(id) || id <= 0) {
      setError("Entry ID is the number in your FPL URL, e.g. /entry/123456/");
      return;
    }
    setError(null);
    setDraft("");
    setIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }

  return (
    <div className="space-y-5">
      <Section
        title="Saved entries"
        subtitle="IDs stay in this browser. The FPL API is public; you do not log in."
        source="fantasy.premierleague.com/api/entry/{id}/"
      >
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            add();
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="FPL entry ID"
            inputMode="numeric"
            className="w-44 rounded-md border border-edge bg-raised px-2.5 py-1.5 font-mono text-[12px] outline-none focus:border-edge-bright"
          />
          <button
            type="submit"
            className="rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model"
          >
            Add team
          </button>
        </form>
        {error && <p className="mt-2 text-[11px] text-risk">{error}</p>}
      </Section>

      {ids.length === 0 && (
        <p className="text-[12px] text-muted">No teams yet. Paste an entry ID from your FPL URL.</p>
      )}

      {ids.map((id) => (
        <TrackedTeam
          key={id}
          id={id}
          gw={gw}
          pool={pool}
          balancedIds={balancedIds}
          onRemove={() => setIds((prev) => prev.filter((x) => x !== id))}
        />
      ))}
    </div>
  );
}

function TrackedTeam({
  id,
  gw,
  pool,
  balancedIds,
  onRemove,
}: {
  id: number;
  gw: number;
  pool: PoolPlayer[];
  balancedIds: number[];
  onRemove: () => void;
}) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [picksOpen, setPicksOpen] = useState(true);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const byId = useMemo(() => new Map(pool.map((p) => [p.id, p])), [pool]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    (async () => {
      try {
        const entryRes = await fpl<Entry>(`entry/${id}`);
        if (cancelled) return;
        if (!entryRes.ok) {
          setStatus("error");
          return;
        }
        setEntry(entryRes.data);

        const eventId = entryRes.data.current_event ?? gw;
        const [picksRes, historyRes] = await Promise.all([
          fpl<{ picks?: Pick[] }>(`entry/${id}/event/${eventId}/picks`),
          fpl<{ current?: HistoryRow[] }>(`entry/${id}/history`),
        ]);
        if (cancelled) return;
        if (picksRes.ok) {
          setPicks(picksRes.data.picks ?? []);
          setPicksOpen(true);
        } else {
          setPicks([]);
          setPicksOpen(false);
        }
        setHistory(historyRes.ok ? (historyRes.data.current ?? []) : []);
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, gw]);

  const squadIds = new Set(picks.map((p) => p.element));
  const xi = picks.filter((p) => p.position <= 11);
  const bench = picks.filter((p) => p.position > 11);
  const xiXp = xi.reduce((s, p) => s + (byId.get(p.element)?.mu ?? 0) * (p.is_captain ? 2 : 1), 0);
  const inBalanced = balancedIds.filter((pid) => !squadIds.has(pid));
  const notBalanced = [...squadIds].filter((pid) => !balancedIds.includes(pid));

  const startNotes = bench.flatMap((b) => {
    const benchP = byId.get(b.element);
    if (benchP?.mu == null) return [];
    const weaker = xi
      .map((s) => byId.get(s.element))
      .filter((s): s is PoolPlayer => !!s && s.pos === benchP.pos && (s.mu ?? 0) + 0.3 < (benchP.mu ?? 0));
    return weaker.slice(0, 1).map((s) => `${benchP.name} (${dec(benchP.mu, 1)}) over ${s.name} (${dec(s.mu, 1)})`);
  });

  const bank = history.find((h) => h.event === gw)?.bank ?? entry?.last_deadline_bank ?? 0;
  const upgrades = [...squadIds]
    .map((pid) => {
      const have = byId.get(pid);
      if (!have || have.cost == null || have.mu == null) return null;
      const better = pool
        .filter(
          (p) =>
            p.pos === have.pos &&
            !squadIds.has(p.id) &&
            p.cost != null &&
            p.mu != null &&
            p.cost <= (have.cost ?? 0) + bank &&
            p.mu > (have.mu ?? 0) + 0.4,
        )
        .sort((a, b) => (b.mu ?? 0) - (a.mu ?? 0))[0];
      if (!better) return null;
      return `${have.name} → ${better.name} (${dec(have.mu, 1)} to ${dec(better.mu, 1)}, ${price(better.cost)})`;
    })
    .filter(Boolean)
    .slice(0, 5);

  return (
    <Section
      title={entry ? `${entry.name}` : `Entry ${id}`}
      subtitle={
        entry
          ? `${[entry.player_first_name, entry.player_last_name].filter(Boolean).join(" ") || "Manager"} · ${entry.summary_overall_points ?? "—"} pts · rank ${entry.summary_overall_rank ?? "—"}`
          : status === "loading"
            ? "Loading official entry…"
            : "Could not load this entry. Check the ID is public."
      }
      source={`api/entry/${id}/`}
      actions={
        <button type="button" onClick={onRemove} className="text-[11px] text-muted hover:text-risk">
          Remove
        </button>
      }
    >
      {status === "error" && (
        <p className="text-[12px] text-risk">The FPL API rejected this entry, or it does not exist.</p>
      )}
      {status === "ready" && (
        <div className="space-y-4">
          {!picksOpen && (
            <p className="text-[12px] leading-relaxed text-muted">
              The team is on the API as <span className="text-ink">{entry?.name}</span>, but FPL
              does not publish the fifteen until the first deadline (GW1, 21 Aug 17:30 UTC).
              After that this card will show picks, xP, and transfer notes automatically.
            </p>
          )}
          {picksOpen && (
            <>
          <div className="grid gap-4 md:grid-cols-2">
            <PickList title="Starting XI" picks={xi} byId={byId} />
            <PickList title="Bench" picks={bench} byId={byId} />
          </div>
          <p className="tnum text-[12px] text-muted">
            Frozen V1 xP of XI + captain: <span className="text-model">{dec(xiXp, 1)}</span>
            {bank ? ` · bank ${price(bank)}` : ""}
          </p>

          <div>
            <div className="label-xs mb-2">Notes vs V1 (not advice to hit confirm)</div>
            <ul className="space-y-1 text-[12px] text-muted">
              {startNotes.length === 0 && upgrades.length === 0 && inBalanced.length === 0 && (
                <li>No obvious xP gap against the frozen pool at this snapshot.</li>
              )}
              {startNotes.map((n) => (
                <li key={n}>Start: {n}</li>
              ))}
              {upgrades.map((n) => (
                <li key={n}>Transfer: {n}</li>
              ))}
              {inBalanced.slice(0, 6).map((pid) => (
                <li key={pid}>
                  In V1 balanced 15, not in this team: {byId.get(pid)?.name ?? pid}
                </li>
              ))}
              {notBalanced.slice(0, 6).map((pid) => (
                <li key={pid}>
                  In this team, not in V1 balanced 15: {byId.get(pid)?.name ?? pid}
                </li>
              ))}
            </ul>
          </div>
            </>
          )}

          {history.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] border-collapse text-[11.5px]">
                <thead>
                  <tr className="border-b border-edge">
                    {["GW", "Pts", "Total", "Rank", "Hits"].map((h) => (
                      <th key={h} className="label-xs py-1.5 pr-3 text-left font-normal">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.slice(-8).map((row) => (
                    <tr key={row.event} className="border-b border-edge/40">
                      <td className="tnum py-1 pr-3">{row.event}</td>
                      <td className="tnum py-1 pr-3">{row.points}</td>
                      <td className="tnum py-1 pr-3">{row.total_points}</td>
                      <td className="tnum py-1 pr-3">{row.rank ?? "—"}</td>
                      <td className="tnum py-1 pr-3">{row.event_transfers_cost || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function PickList({
  title,
  picks,
  byId,
}: {
  title: string;
  picks: Pick[];
  byId: Map<number, PoolPlayer>;
}) {
  return (
    <div>
      <div className="label-xs mb-2">{title}</div>
      <ul className="space-y-px">
        {picks.map((p) => {
          const player = byId.get(p.element);
          return (
            <li
              key={p.element}
              className="flex items-baseline justify-between gap-2 rounded px-1.5 py-1 text-[12px] odd:bg-raised/40"
            >
              <span className="truncate">
                {player?.name ?? `#${p.element}`}
                {p.is_captain && <span className="ml-1 text-[9px] font-bold text-model">C</span>}
                {p.is_vice_captain && !p.is_captain && (
                  <span className="ml-1 text-[9px] font-bold text-model">V</span>
                )}
                <span className="ml-1.5 text-[10px] text-faint">
                  {player?.teamCode ?? ""} {player?.pos ?? ""}
                </span>
              </span>
              <span className="tnum shrink-0 text-model">{dec(player?.mu, 1)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
