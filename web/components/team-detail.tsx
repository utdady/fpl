"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { EntryPitch } from "./entry-pitch";
import { GwEdgePanel } from "./gw-edge-panel";
import { Section } from "./ui/section";
import { dec, price } from "@/lib/format";
import {
  fetchEntryBundle,
  fplFetch,
  type FplEntry,
  type FplHistoryRow,
  type FplPick,
  type FplTransfer,
} from "@/lib/fpl-entry";
import {
  notesVsMine,
  notesVsV1,
  squadOverlap,
  xiCaptainTotals,
  type ComparePoolPlayer,
} from "@/lib/team-compare";
import { LiveProvider } from "@/lib/live-context";
import { useGwEdge } from "@/lib/use-gw-edge";
import {
  loadTracked,
  saveTracked,
  setCompareId,
  type TrackedState,
} from "@/lib/tracked-teams";

export function TeamDetail({
  id,
  gw,
  season,
  pool,
  balancedIds,
  liveEnabled = false,
}: {
  id: number;
  gw: number;
  season: string;
  pool: ComparePoolPlayer[];
  balancedIds: number[];
  liveEnabled?: boolean;
}) {
  const [tracked, setTracked] = useState<TrackedState | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [entry, setEntry] = useState<FplEntry | null>(null);
  const [picks, setPicks] = useState<FplPick[]>([]);
  const [picksOpen, setPicksOpen] = useState(false);
  const [history, setHistory] = useState<FplHistoryRow[]>([]);
  const [transfers, setTransfers] = useState<FplTransfer[]>([]);
  const [mineBundle, setMineBundle] = useState<{
    entry: FplEntry;
    picks: FplPick[];
  } | null>(null);
  const [mineNames, setMineNames] = useState<Record<number, string>>({});

  const byId = useMemo(() => new Map(pool.map((p) => [p.id, p])), [pool]);
  const isMine = tracked?.mine.includes(id) ?? false;
  const compareId = tracked?.compareId ?? null;

  useEffect(() => {
    const s = loadTracked();
    setTracked(s);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    (async () => {
      try {
        const bundle = await fetchEntryBundle(id, gw);
        if (cancelled) return;
        setEntry(bundle.entry);
        setPicks(bundle.picks);
        setPicksOpen(bundle.picksOpen);
        setHistory(bundle.history);
        const tr = await fplFetch<FplTransfer[]>(`entry/${id}/transfers`);
        if (!cancelled && tr.ok) setTransfers(tr.data.slice(0, 12));
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, gw]);

  useEffect(() => {
    if (!tracked || isMine || compareId == null) {
      setMineBundle(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const bundle = await fetchEntryBundle(compareId, gw);
        if (cancelled) return;
        setMineBundle({ entry: bundle.entry, picks: bundle.picks });
        setMineNames((prev) => ({ ...prev, [compareId]: bundle.entry.name }));
      } catch {
        if (!cancelled) setMineBundle(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tracked, isMine, compareId, gw]);

  useEffect(() => {
    if (!tracked?.mine.length) return;
    let cancelled = false;
    (async () => {
      const next: Record<number, string> = {};
      await Promise.all(
        tracked.mine.map(async (mid) => {
          try {
            const b = await fetchEntryBundle(mid, gw);
            next[mid] = b.entry.name;
          } catch {
            next[mid] = `Entry ${mid}`;
          }
        }),
      );
      if (!cancelled) setMineNames((prev) => ({ ...prev, ...next }));
    })();
    return () => {
      cancelled = true;
    };
  }, [tracked?.mine, gw]);

  function patchTracked(next: TrackedState) {
    setTracked(next);
    saveTracked(next);
  }

  const bank =
    history.find((h) => h.event === gw)?.bank ?? entry?.last_deadline_bank ?? 0;
  const totals = xiCaptainTotals(picks, byId);
  const v1Notes =
    picksOpen && picks.length
      ? notesVsV1(picks, pool, balancedIds, bank, (n) => dec(n, 1), (n) => price(n))
      : null;
  const v1NoteItems =
    v1Notes == null
      ? []
      : [
          ...v1Notes.startNotes.map((n) => `Start: ${n}`),
          ...v1Notes.upgrades.map((n) => `Transfer: ${n}`),
          ...v1Notes.inBalanced.slice(0, 6).map(
            (pid) => `In V1 balanced 15, not here: ${byId.get(pid)?.name ?? pid}`,
          ),
          ...v1Notes.notBalanced.slice(0, 6).map(
            (pid) => `Here, not in V1 balanced 15: ${byId.get(pid)?.name ?? pid}`,
          ),
        ];

  return (
    <LiveProvider gw={gw} enabled={liveEnabled}>
      <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/teams" className="text-[11px] text-muted hover:text-ink">
            ← Teams
          </Link>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">
            {entry?.name ?? `Entry ${id}`}
          </h1>
          <p className="mt-1 text-[12px] text-muted">
            {status === "loading" && "Loading official entry…"}
            {status === "error" && "Could not load this entry."}
            {status === "ready" && entry && (
              <>
                {[entry.player_first_name, entry.player_last_name].filter(Boolean).join(" ") ||
                  "Manager"}
                {" · "}
                {entry.summary_overall_points ?? "—"} pts · rank{" "}
                {entry.summary_overall_rank ?? "—"}
                {isMine ? " · yours" : ""}
              </>
            )}
          </p>
        </div>
        {!isMine && tracked && tracked.mine.length > 1 && (
          <label className="flex items-center gap-2 text-[12px] text-muted">
            Baseline
            <select
              value={compareId ?? ""}
              onChange={(e) =>
                patchTracked(
                  setCompareId(tracked, e.target.value ? Number(e.target.value) : null),
                )
              }
              className="rounded-md border border-edge bg-raised px-2 py-1 text-[12px]"
            >
              {tracked.mine.map((mid) => (
                <option key={mid} value={mid}>
                  {mineNames[mid] ?? `Entry ${mid}`}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {status === "ready" && (
        <>
          <p className="tnum text-[12px] text-muted">
            Frozen V1 xP of XI + captain:{" "}
            <span className="text-model">{dec(totals.mu, 1)}</span>
            {totals.sigma != null ? (
              <span className="text-faint"> ± {dec(totals.sigma, 1)}</span>
            ) : null}
            {bank ? ` · bank ${price(bank)}` : ""}
          </p>

          {!picksOpen && (
            <p className="text-[12px] leading-relaxed text-muted">
              FPL has not published this gameweek&apos;s fifteen yet (usually after the
              deadline). Stats above still come from the entry endpoint.
            </p>
          )}

          {picksOpen && picks.length > 0 && (
            <Section title="Pitch" subtitle="Live FPL picks scored with frozen V1 μ." source={`api/entry/${id}/event/.../picks`}>
              <EntryPitch
                picks={picks}
                pool={pool}
                season={season}
                gw={gw}
              />
            </Section>
          )}

          {isMine && v1Notes && (
            <CollapsibleNotes
              title="Notes vs V1"
              subtitle="Not advice to hit confirm."
              items={v1NoteItems}
              empty="No obvious xP gap against the frozen pool at this snapshot."
              source="frozen predictions + V1 balanced 15"
            />
          )}

          {!isMine && (
            <ComparePanel
              rivalPicks={picks}
              rivalOpen={picksOpen}
              mineBundle={mineBundle}
              compareId={compareId}
              hasMine={!!tracked?.mine.length}
              byId={byId}
              liveEnabled={liveEnabled}
              rivalName={entry?.name ?? `Entry ${id}`}
            />
          )}

          {history.length > 0 && (
            <details className="group rounded-md border border-edge bg-raised/30">
              <summary className="cursor-pointer list-none px-3 py-2 text-[12px] text-muted marker:content-none [&::-webkit-details-marker]:hidden">
                <span className="font-medium text-ink">Recent gameweeks</span>
                <span className="tnum ml-2 text-[11px] text-faint">
                  {Math.min(history.length, 8)}
                </span>
              </summary>
              <div className="border-t border-edge px-3 py-3">
                <HistoryTable rows={history.slice(-8)} />
              </div>
            </details>
          )}

          {transfers.length > 0 && (
            <details className="group rounded-md border border-edge bg-raised/30">
              <summary className="cursor-pointer list-none px-3 py-2 text-[12px] text-muted marker:content-none [&::-webkit-details-marker]:hidden">
                <span className="font-medium text-ink">Recent transfers</span>
                <span className="tnum ml-2 text-[11px] text-faint">{transfers.length}</span>
              </summary>
              <ul className="space-y-1 border-t border-edge px-3 py-3 text-[12px] text-muted">
                {transfers.map((t, i) => (
                  <li key={`${t.time}-${i}`}>
                    GW{t.event}: {byId.get(t.element_out)?.name ?? `#${t.element_out}`} →{" "}
                    {byId.get(t.element_in)?.name ?? `#${t.element_in}`}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      </div>
    </LiveProvider>
  );
}

function ComparePanel({
  rivalPicks,
  rivalOpen,
  mineBundle,
  compareId,
  hasMine,
  byId,
  liveEnabled,
  rivalName,
}: {
  rivalPicks: FplPick[];
  rivalOpen: boolean;
  mineBundle: { entry: FplEntry; picks: FplPick[] } | null;
  compareId: number | null;
  hasMine: boolean;
  byId: Map<number, ComparePoolPlayer>;
  liveEnabled: boolean;
  rivalName: string;
}) {
  if (!hasMine || compareId == null) {
    return (
      <Section title="Compare" subtitle="Mark at least one team as Mine on the Teams list.">
        <p className="text-[12px] text-muted">
          No baseline yet. Go back to Teams, check Mine on your entry, then reopen this rival.
        </p>
      </Section>
    );
  }

  if (!mineBundle) {
    return (
      <Section title="Compare" subtitle={`vs entry ${compareId}`}>
        <p className="text-[12px] text-muted">Loading your team…</p>
      </Section>
    );
  }

  if (!rivalOpen || rivalPicks.length === 0 || mineBundle.picks.length === 0) {
    return (
      <Section title="Compare" subtitle={`vs ${mineBundle.entry.name}`}>
        <p className="text-[12px] text-muted">
          Need published picks on both sides before overlap and GW edge.
        </p>
      </Section>
    );
  }

  return (
    <ComparePanelReady
      rivalPicks={rivalPicks}
      minePicks={mineBundle.picks}
      mineName={mineBundle.entry.name}
      rivalName={rivalName}
      byId={byId}
      liveEnabled={liveEnabled}
    />
  );
}

function ComparePanelReady({
  rivalPicks,
  minePicks,
  mineName,
  rivalName,
  byId,
  liveEnabled,
}: {
  rivalPicks: FplPick[];
  minePicks: FplPick[];
  mineName: string;
  rivalName: string;
  byId: Map<number, ComparePoolPlayer>;
  liveEnabled: boolean;
}) {
  const edge = useGwEdge(minePicks, rivalPicks, byId, liveEnabled);
  const overlap = squadOverlap(minePicks, rivalPicks);
  const vsMine = notesVsMine(rivalPicks, minePicks, byId, (n) => dec(n, 1));
  const notes = [
    ...vsMine.startGaps,
    ...vsMine.onlyThem.map((n) => `Only them: ${n}`),
    ...vsMine.onlyMe.map((n) => `Only you: ${n}`),
  ];
  const nameOf = (pid: number | null) =>
    pid == null ? "—" : (byId.get(pid)?.name ?? `#${pid}`);

  return (
    <Section
      title="Compare"
      subtitle={`vs your ${mineName} · ${edge.live ? "live + projected" : "frozen V1 μ/σ"} · this GW only`}
      source="entry picks + predictions.json"
    >
      <div className="space-y-4 text-[12px]">
        <div className="grid gap-3 sm:grid-cols-3">
          <OverlapCol title="Both" ids={overlap.both} byId={byId} />
          <OverlapCol title="Only them" ids={overlap.onlyRival} byId={byId} />
          <OverlapCol title="Only you" ids={overlap.onlyMine} byId={byId} />
        </div>

        <p className="text-muted">
          Captain: them <span className="text-ink">{nameOf(overlap.rivalCap)}</span>
          {" · "}
          you <span className="text-ink">{nameOf(overlap.mineCap)}</span>
          {" · "}
          Vice: them {nameOf(overlap.rivalVc)} · you {nameOf(overlap.mineVc)}
        </p>

        <p className="tnum text-muted">
          XI+C total: {rivalName}{" "}
          <span className="text-model">{dec(edge.rivalDisplay.mu, 1)}</span>
          {edge.rivalDisplay.sigma != null && edge.rivalDisplay.sigma > 0 ? (
            <span className="text-faint"> ± {dec(edge.rivalDisplay.sigma, 1)}</span>
          ) : null}
          {" · "}
          you{" "}
          <span className="text-model">{dec(edge.mineDisplay.mu, 1)}</span>
          {edge.mineDisplay.sigma != null && edge.mineDisplay.sigma > 0 ? (
            <span className="text-faint"> ± {dec(edge.mineDisplay.sigma, 1)}</span>
          ) : null}
          {" · "}
          gap{" "}
          <span className="text-ink">
            {edge.d >= 0 ? "+" : ""}
            {dec(edge.d, 1)}
          </span>
        </p>

        <GwEdgePanel
          edge={edge}
          mineLabel="You"
          rivalLabel={rivalName.split(" ")[0] ?? "Them"}
        />

        <CollapsibleNotes
          title="Notes vs my team"
          items={notes}
          empty="Squads look aligned on the frozen pool snapshot."
        />
      </div>
    </Section>
  );
}

function OverlapCol({
  title,
  ids,
  byId,
}: {
  title: string;
  ids: number[];
  byId: Map<number, ComparePoolPlayer>;
}) {
  return (
    <div>
      <div className="label-xs mb-1">
        {title}{" "}
        <span className="tnum text-faint">{ids.length}</span>
      </div>
      <ul className="space-y-0.5 text-muted">
        {ids.length === 0 && <li className="text-faint">—</li>}
        {ids.slice(0, 10).map((pid) => (
          <li key={pid} className="truncate">
            {byId.get(pid)?.name ?? `#${pid}`}
          </li>
        ))}
        {ids.length > 10 && (
          <li className="text-faint">+{ids.length - 10} more</li>
        )}
      </ul>
    </div>
  );
}

function CollapsibleNotes({
  title,
  subtitle,
  items,
  empty,
  source,
}: {
  title: string;
  subtitle?: string;
  items: string[];
  empty: string;
  source?: string;
}) {
  return (
    <details className="group rounded-md border border-edge bg-raised/30">
      <summary className="cursor-pointer list-none px-3 py-2 text-[12px] text-muted marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="font-medium text-ink">{title}</span>
        <span className="tnum ml-2 text-[11px] text-faint">{items.length}</span>
      </summary>
      <div className="border-t border-edge px-3 py-3">
        {subtitle && (
          <p className="mb-2 text-[11px] leading-relaxed text-muted">{subtitle}</p>
        )}
        <NotesList items={items} empty={empty} />
        {source && (
          <p className="mt-3 font-mono text-[10px] text-faint">
            source: <span className="text-muted">{source}</span>
          </p>
        )}
      </div>
    </details>
  );
}

function NotesList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-[12px] text-muted">{empty}</p>;
  }
  return (
    <ul className="space-y-1 text-[12px] text-muted">
      {items.map((n) => (
        <li key={n}>{n}</li>
      ))}
    </ul>
  );
}

function HistoryTable({ rows }: { rows: FplHistoryRow[] }) {
  return (
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
          {rows.map((row) => (
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
  );
}
