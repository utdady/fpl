"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MeGate } from "./me-gate";
import {
  accountJson,
  type BootstrapElement,
  type BootstrapEvent,
  type BootstrapStatic,
  type MyTeam,
  type MyTeamPick,
} from "@/lib/fpl-account";
import { fplFetch, type FplEntry, type FplHistoryRow } from "@/lib/fpl-entry";
import { dec, formatDeadline, pct, price } from "@/lib/format";
import { ELEMENT_POS } from "@/lib/fpl-rules";
import type { ComparePoolPlayer } from "@/lib/team-compare";
import { useSession } from "@/lib/use-session";

const STATUS_LABEL: Record<string, string> = {
  a: "Available",
  d: "Doubtful",
  i: "Injured",
  s: "Suspended",
  u: "Unavailable",
  n: "Not available",
};

type DreamPick = { element: number; points: number; position: number };

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function useCountdown(iso: string | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!iso) return null;
  const diff = Math.max(0, new Date(iso).getTime() - now);
  const total = Math.floor(diff / 1000);
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
}

function PanelCard({
  title,
  href,
  linkLabel,
  className = "",
  children,
}: {
  title: string;
  href?: string;
  linkLabel?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`panel p-5 md:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
        {href && (
          <Link
            href={href}
            className="shrink-0 rounded-full border border-edge px-3 py-1 text-[11px] text-muted hover:border-edge-bright hover:text-ink"
          >
            {linkLabel ?? "View"} <span aria-hidden>›</span>
          </Link>
        )}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-raised/70 px-3 py-3">
      <div className="label-xs">{label}</div>
      <div className="tnum mt-1.5 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function PlayerRow({
  el,
  teams,
  right,
  arrow,
  flag,
}: {
  el: BootstrapElement;
  teams: Map<number, string>;
  right: React.ReactNode;
  arrow?: "in" | "out";
  flag?: "red" | "amber";
}) {
  const pos = ELEMENT_POS[el.element_type] ?? "MID";
  const club = teams.get(el.team) ?? "";
  return (
    <li className="flex items-center gap-2.5 border-b border-edge py-2.5 last:border-0">
      {flag && (
        <span
          className={`text-[12px] ${flag === "red" ? "text-risk" : "text-oracle"}`}
          title={STATUS_LABEL[el.status] ?? el.status}
        >
          ▲
        </span>
      )}
      {arrow && (
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${
            arrow === "in" ? "bg-actual/20 text-actual" : "bg-risk/20 text-risk"
          }`}
          aria-label={arrow === "in" ? "in" : "out"}
        >
          {arrow === "in" ? "→" : "←"}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold">{el.web_name}</div>
        <div className="text-[11px] text-muted">
          {club} {pos}
        </div>
      </div>
      <span className="tnum shrink-0 text-[13px]">{right}</span>
    </li>
  );
}

type SquadSpot = {
  pick: MyTeamPick;
  el: BootstrapElement;
};

function isFlagged(el: BootstrapElement) {
  return (
    el.status !== "a" ||
    Boolean(el.news) ||
    (el.chance_of_playing_this_round != null && el.chance_of_playing_this_round < 100)
  );
}

function flagPriority(el: BootstrapElement) {
  if (el.status === "i" || el.status === "s") return 0;
  if ((el.chance_of_playing_this_round ?? 100) <= 25) return 1;
  if (el.status !== "a") return 2;
  if ((el.chance_of_playing_this_round ?? 100) < 100) return 3;
  if (el.news) return 4;
  return 100;
}

function buildSquadSpots(
  picks: MyTeamPick[],
  elements: Map<number, BootstrapElement>,
): SquadSpot[] {
  return [...picks]
    .sort((a, b) => a.position - b.position)
    .map((pick) => {
      const el = elements.get(pick.element);
      return el ? { pick, el } : null;
    })
    .filter((x): x is SquadSpot => x != null);
}

function spotlightIndex(spots: SquadSpot[]) {
  let best = 0;
  let bestScore = Number.POSITIVE_INFINITY;
  for (let i = 0; i < spots.length; i++) {
    const { pick, el } = spots[i];
    let score = 50 + pick.position;
    if (isFlagged(el)) score = flagPriority(el);
    else if (pick.is_captain) score = 10;
    else if (pick.is_vice_captain) score = 20;
    else if (pick.position <= 11) score = 30 + (20 - (el.now_cost ?? 0) / 10);
    if (score < bestScore) {
      bestScore = score;
      best = i;
    }
  }
  return best;
}

function spotReason(spot: SquadSpot) {
  const { pick, el } = spot;
  if (isFlagged(el)) {
    if (el.status === "i") return "Injured";
    if (el.status === "s") return "Suspended";
    if ((el.chance_of_playing_this_round ?? 100) < 100) {
      return `${el.chance_of_playing_this_round}% chance`;
    }
    return STATUS_LABEL[el.status] ?? "Availability";
  }
  if (pick.is_captain) return "Captain";
  if (pick.is_vice_captain) return "Vice captain";
  if (pick.position > 11) return "Bench";
  return "Starting XI";
}

function SquadSpotlight({
  spots,
  teams,
  projections,
}: {
  spots: SquadSpot[];
  teams: Map<number, string>;
  projections: Map<number, ComparePoolPlayer>;
}) {
  const [index, setIndex] = useState(() => spotlightIndex(spots));
  const [paused, setPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    setIndex(spotlightIndex(spots));
  }, [spots]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (spots.length < 2 || paused || reducedMotion) return;
    const timer = setInterval(() => {
      if (document.hidden) return;
      setIndex((i) => (i + 1) % spots.length);
    }, 7000);
    return () => clearInterval(timer);
  }, [spots.length, paused, reducedMotion]);

  if (spots.length === 0) return null;

  const spot = spots[Math.min(index, spots.length - 1)]!;
  const { pick, el } = spot;
  const club = teams.get(el.team) ?? "";
  const pos = ELEMENT_POS[el.element_type] ?? "MID";
  const flagged = isFlagged(el);
  const reason = spotReason(spot);
  const proj = projections.get(el.id);
  const mu = proj?.mu ?? null;
  const pStart = proj?.pStart ?? null;

  const step = (dir: -1 | 1) => {
    setIndex((i) => (i + dir + spots.length) % spots.length);
  };

  return (
    <div
      className="flex flex-col rounded-xl border border-white/15 bg-black/25 p-3.5 backdrop-blur-[2px] sm:p-4"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setPaused(false);
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="label-xs text-ink/65">Squad</span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            flagged
              ? "bg-risk/25 text-risk"
              : pick.is_captain
                ? "bg-model/20 text-model"
                : "bg-white/10 text-ink/75"
          }`}
        >
          {reason}
        </span>
      </div>

      <div className="mt-2.5">
        <div className="truncate text-[17px] font-semibold tracking-tight">{el.web_name}</div>
        <div className="mt-0.5 text-[12px] text-ink/70">
          {club} · {pos}
          {pick.is_captain ? " · C" : pick.is_vice_captain ? " · V" : ""}
          {pick.position > 11 ? " · Bench" : ""}
        </div>

        <div className="mt-2.5 grid grid-cols-4 gap-1.5">
          <div className="rounded-md bg-black/20 px-1.5 py-1.5 text-center">
            <div className="label-xs text-ink/50">V1 xP</div>
            <div className="tnum mt-0.5 text-[13px] font-semibold text-model">
              {dec(mu, 1)}
              {pick.is_captain && mu != null ? (
                <span className="text-[9px] font-medium text-model/70">×2</span>
              ) : null}
            </div>
          </div>
          <div className="rounded-md bg-black/20 px-1.5 py-1.5 text-center">
            <div className="label-xs text-ink/50">p_start</div>
            <div className="tnum mt-0.5 text-[13px] font-semibold">{pct(pStart, 0)}</div>
          </div>
          <div className="rounded-md bg-black/20 px-1.5 py-1.5 text-center">
            <div className="label-xs text-ink/50">Price</div>
            <div className="tnum mt-0.5 text-[13px] font-semibold">{price(el.now_cost)}</div>
          </div>
          <div className="rounded-md bg-black/20 px-1.5 py-1.5 text-center">
            <div className="label-xs text-ink/50">Owned</div>
            <div className="tnum mt-0.5 text-[13px] font-semibold">{el.selected_by_percent}%</div>
          </div>
        </div>

        {(el.event_points != null || el.news) && (
          <div className="mt-2 space-y-1">
            {el.event_points != null ? (
              <p className="tnum text-[11px] text-ink/60">{el.event_points} pts this GW</p>
            ) : null}
            {el.news ? (
              <p className="line-clamp-1 text-[11px] leading-snug text-ink/65">{el.news}</p>
            ) : null}
          </div>
        )}
      </div>

      {spots.length > 1 ? (
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-white/10 pt-2.5">
          <button
            type="button"
            aria-label="Previous player"
            onClick={() => step(-1)}
            className="flex h-7 w-7 items-center justify-center rounded-full border border-white/15 text-[13px] text-ink/80 hover:border-white/35 hover:bg-white/10"
          >
            ‹
          </button>
          <span className="tnum text-[11px] text-ink/60">
            {index + 1} / {spots.length}
          </span>
          <button
            type="button"
            aria-label="Next player"
            onClick={() => step(1)}
            className="flex h-7 w-7 items-center justify-center rounded-full border border-white/15 text-[13px] text-ink/80 hover:border-white/35 hover:bg-white/10"
          >
            ›
          </button>
        </div>
      ) : null}
    </div>
  );
}

function StatusHero({
  teamName,
  manager,
  gw,
  points,
  average,
  highest,
  events,
  squadSpots,
  teams,
  projections,
}: {
  teamName: string;
  manager: string;
  gw: number;
  points: number | null;
  average: number | null;
  highest: number | null;
  events: BootstrapEvent[];
  squadSpots: SquadSpot[];
  teams: Map<number, string>;
  projections: Map<number, ComparePoolPlayer>;
}) {
  const next = events.find((e) => e.is_next) ?? events.find((e) => !e.finished);
  const upcoming = events
    .filter((e) => !e.finished && e.id !== next?.id && e.id > (next?.id ?? 0))
    .slice(0, 3);
  const clock = useCountdown(next?.deadline_time ?? null);

  return (
    <section
      className="overflow-hidden rounded-xl p-5 text-ink md:p-6"
      style={{
        background:
          "linear-gradient(115deg, color-mix(in oklab, var(--color-model) 42%, #1a6b8a), var(--color-plum) 58%)",
      }}
    >
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(240px,0.42fr)] md:items-start md:gap-8 lg:gap-10">
        <div
          className={
            squadSpots.length > 0
              ? "grid gap-4 sm:grid-cols-[minmax(0,0.9fr)_minmax(300px,1.4fr)] sm:items-start lg:gap-5 lg:grid-cols-[minmax(0,0.85fr)_minmax(320px,1.55fr)]"
              : undefined
          }
        >
          <div>
            <div className="text-[22px] font-semibold tracking-tight">{teamName}</div>
            {manager ? <div className="mt-1 text-[13px] text-ink/80">{manager}</div> : null}

            <p className="mt-5 text-[13px] font-medium text-ink/85">Gameweek {gw}</p>
            <div className="mt-3 flex flex-wrap items-end gap-x-8 gap-y-3">
              <div>
                <div className="tnum text-2xl font-semibold">{average ?? "—"}</div>
                <div className="mt-1 text-[11px] text-ink/70">Average</div>
              </div>
              <Link href="/me/statistics" className="block">
                <div className="tnum text-4xl font-bold leading-none">{points ?? "—"}</div>
                <div className="mt-1 text-[11px] text-ink/70">
                  Points <span aria-hidden>›</span>
                </div>
              </Link>
              <div>
                <div className="tnum text-2xl font-semibold">{highest ?? "—"}</div>
                <div className="mt-1 text-[11px] text-ink/70">Highest</div>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <Link
                href="/me/pick-team"
                className="inline-flex items-center justify-center rounded-full border border-model/35 bg-plum-deep/70 px-5 py-2.5 text-[13px] font-medium hover:border-model/70 hover:bg-plum-deep"
              >
                Pick Team
              </Link>
              <Link
                href="/me/transfers"
                className="inline-flex items-center justify-center rounded-full border border-white/15 bg-plum-deep/55 px-5 py-2.5 text-[13px] font-medium hover:border-white/35 hover:bg-plum-deep/80"
              >
                Transfers
              </Link>
            </div>
          </div>

          {squadSpots.length > 0 ? (
            <SquadSpotlight
              spots={squadSpots}
              teams={teams}
              projections={projections}
            />
          ) : null}
        </div>

        <div className="md:border-l md:border-white/15 md:pl-6 lg:pl-8">
          <div className="label-xs text-ink/70">Next deadline</div>
          {next ? (
            <>
              <p className="mt-1.5 text-[15px] font-semibold">{next.name}</p>
              {clock && (
                <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                  {(
                    [
                      [clock.days, "Days"],
                      [clock.hours, "Hours"],
                      [clock.minutes, "Minutes"],
                      [clock.seconds, "Seconds"],
                    ] as const
                  ).map(([n, label]) => (
                    <div key={label} className="rounded-lg bg-black/20 px-1 py-2.5">
                      <div className="tnum text-xl font-semibold">{pad(n)}</div>
                      <div className="mt-1 text-[9px] tracking-wide text-ink/60 uppercase">{label}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="mt-1.5 text-[13px] text-ink/70">No upcoming deadline.</p>
          )}
          {upcoming.length > 0 && (
            <ul className="mt-4 space-y-2">
              {upcoming.map((e) => (
                <li key={e.id} className="flex items-baseline justify-between gap-3 text-[12px]">
                  <span className="font-medium text-ink/90">{e.name}</span>
                  <span className="tnum shrink-0 text-ink/70">
                    {e.deadline_time ? formatDeadline(e.deadline_time) : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

export function MeStatusDashboard({ pool }: { pool: ComparePoolPlayer[] }) {
  return (
    <MeGate>
      <StatusInner pool={pool} />
    </MeGate>
  );
}

function StatusInner({ pool }: { pool: ComparePoolPlayer[] }) {
  const session = useSession();
  const [entry, setEntry] = useState<FplEntry | null>(null);
  const [history, setHistory] = useState<FplHistoryRow[]>([]);
  const [boot, setBoot] = useState<BootstrapStatic | null>(null);
  const [team, setTeam] = useState<MyTeam | null>(null);
  const [dream, setDream] = useState<DreamPick[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!session.entryId) return;
    setLoading(true);
    setError(null);
    const [entryRes, histRes, bootRes, teamRes] = await Promise.all([
      fplFetch<FplEntry>(`entry/${session.entryId}`),
      fplFetch<{ current?: FplHistoryRow[] }>(`entry/${session.entryId}/history`),
      fplFetch<BootstrapStatic>("bootstrap-static"),
      accountJson<MyTeam>("/api/account/team"),
    ]);
    if (!entryRes.ok) {
      setLoading(false);
      setError("Could not load your entry");
      return;
    }
    setEntry(entryRes.data);
    setHistory(histRes.ok ? (histRes.data.current ?? []) : []);
    if (bootRes.ok) setBoot(bootRes.data);
    if (teamRes.ok) setTeam(teamRes.data);

    const gw = entryRes.data.current_event ?? 1;
    const dreamRes = await fplFetch<{ team?: DreamPick[] }>(`dream-team/${gw}`);
    setDream(dreamRes.ok ? (dreamRes.data.team ?? []) : []);
    setLoading(false);
  }, [session.entryId]);

  useEffect(() => {
    void load();
  }, [load]);

  const events = boot?.events ?? [];
  const gw = entry?.current_event ?? events.find((e) => e.is_current)?.id ?? 1;
  const eventRow = events.find((e) => e.id === gw);
  const latestHist = history.find((h) => h.event === gw) ?? history.at(-1);
  const seasonTransfers = history.reduce((sum, h) => sum + (h.event_transfers ?? 0), 0);

  const teams = useMemo(
    () => new Map((boot?.teams ?? []).map((t) => [t.id, t.short_name])),
    [boot],
  );
  const elements = useMemo(
    () => new Map((boot?.elements ?? []).map((e) => [e.id, e])),
    [boot],
  );

  const topIn = useMemo(
    () =>
      [...(boot?.elements ?? [])]
        .sort((a, b) => (b.transfers_in_event ?? 0) - (a.transfers_in_event ?? 0))
        .slice(0, 5),
    [boot],
  );
  const topOut = useMemo(
    () =>
      [...(boot?.elements ?? [])]
        .sort((a, b) => (b.transfers_out_event ?? 0) - (a.transfers_out_event ?? 0))
        .slice(0, 5),
    [boot],
  );
  const totw = useMemo(
    () =>
      [...dream]
        .sort((a, b) => a.position - b.position)
        .map((p) => ({ pick: p, el: elements.get(p.element) }))
        .filter((x): x is { pick: DreamPick; el: BootstrapElement } => x.el != null)
        .slice(0, 11),
    [dream, elements],
  );
  const availability = useMemo(
    () =>
      [...(boot?.elements ?? [])]
        .filter(
          (e) =>
            e.status !== "a" ||
            Boolean(e.news) ||
            (e.chance_of_playing_this_round != null && e.chance_of_playing_this_round < 100),
        )
        .sort((a, b) => (a.chance_of_playing_this_round ?? 100) - (b.chance_of_playing_this_round ?? 100))
        .slice(0, 12),
    [boot],
  );

  const squadSpots = useMemo(
    () => buildSquadSpots(team?.picks ?? [], elements),
    [team, elements],
  );
  const projections = useMemo(
    () => new Map(pool.map((p) => [p.id, p])),
    [pool],
  );

  if (loading) return <p className="text-[12px] text-muted">Loading status…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  return (
    <div className="w-full">
      <StatusHero
        teamName={session.name ?? entry?.name ?? "My team"}
        manager={
          session.playerName ||
          [entry?.player_first_name, entry?.player_last_name].filter(Boolean).join(" ") ||
          ""
        }
        gw={gw}
        points={latestHist?.points ?? entry?.summary_overall_points ?? null}
        average={eventRow?.average_entry_score ?? null}
        highest={eventRow?.highest_score ?? null}
        events={events}
        squadSpots={squadSpots}
        teams={teams}
        projections={projections}
      />

      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-12 md:gap-5">
        <PanelCard
          className="md:col-span-4"
          title="Points & Rankings"
          href="/me/statistics"
          linkLabel="Gameweek History"
        >
          <div className="grid grid-cols-2 gap-2.5">
            <StatTile label="Overall points" value={entry?.summary_overall_points ?? "—"} />
            <StatTile
              label="Overall rank"
              value={entry?.summary_overall_rank?.toLocaleString() ?? "—"}
            />
            <StatTile label="Total players" value={boot?.total_players?.toLocaleString() ?? "—"} />
            <StatTile label="Gameweek points" value={latestHist?.points ?? "—"} />
          </div>
        </PanelCard>

        <PanelCard
          className="md:col-span-4"
          title="Transfers"
          href="/me/transfers"
          linkLabel="Transfer History"
        >
          <div className="grid grid-cols-2 gap-2.5">
            <StatTile
              label="This gameweek"
              value={team?.transfers.made ?? latestHist?.event_transfers ?? 0}
            />
            <StatTile label="Season total" value={seasonTransfers} />
          </div>
        </PanelCard>

        <PanelCard className="md:col-span-4" title="Finance" href="/me/prices">
          <div className="grid grid-cols-2 gap-2.5">
            <StatTile label="Squad value" value={price(team?.transfers.value)} />
            <StatTile label="In the bank" value={price(team?.transfers.bank)} />
          </div>
        </PanelCard>

        <PanelCard className="md:col-span-6" title="Top transfers in" href="/me/transfers">
          <div className="mb-1 flex justify-between text-[11px] text-faint">
            <span>Player</span>
            <span>Transferred</span>
          </div>
          <ul>
            {topIn.map((el) => (
              <PlayerRow
                key={el.id}
                el={el}
                teams={teams}
                arrow="in"
                right={(el.transfers_in_event ?? 0).toLocaleString()}
              />
            ))}
          </ul>
        </PanelCard>

        <PanelCard className="md:col-span-6" title="Top transfers out" href="/me/transfers">
          <div className="mb-1 flex justify-between text-[11px] text-faint">
            <span>Player</span>
            <span>Transferred</span>
          </div>
          <ul>
            {topOut.map((el) => (
              <PlayerRow
                key={el.id}
                el={el}
                teams={teams}
                arrow="out"
                right={(el.transfers_out_event ?? 0).toLocaleString()}
              />
            ))}
          </ul>
        </PanelCard>

        <PanelCard className="md:col-span-5" title="Team of the Week">
          <div className="mb-1 flex justify-between text-[11px] text-faint">
            <span>Player</span>
            <span>Pts</span>
          </div>
          {totw.length === 0 ? (
            <p className="text-[12px] text-muted">Not published for this gameweek yet.</p>
          ) : (
            <ul>
              {totw.map(({ pick, el }) => (
                <PlayerRow
                  key={el.id}
                  el={el}
                  teams={teams}
                  flag={
                    el.status !== "a"
                      ? el.status === "i" || el.status === "s"
                        ? "red"
                        : "amber"
                      : undefined
                  }
                  right={pick.points}
                />
              ))}
            </ul>
          )}
        </PanelCard>

        <PanelCard className="md:col-span-7" title="Player availability" href="/me/injuries">
          <div className="mb-1 hidden justify-between text-[11px] text-faint sm:flex">
            <span>Player</span>
            <span>News</span>
          </div>
          {availability.length === 0 ? (
            <p className="text-[12px] text-muted">No injury news right now.</p>
          ) : (
            <ul>
              {availability.map((el) => (
                <li
                  key={el.id}
                  className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 border-b border-edge py-2.5 last:border-0 sm:grid-cols-[auto_10rem_minmax(0,1fr)]"
                >
                  <span
                    className={`mt-0.5 text-[12px] ${
                      el.status === "i" ||
                      el.status === "s" ||
                      (el.chance_of_playing_this_round ?? 100) <= 25
                        ? "text-risk"
                        : "text-oracle"
                    }`}
                  >
                    ▲
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-semibold">{el.web_name}</div>
                    <div className="text-[11px] text-muted">
                      {teams.get(el.team)} {ELEMENT_POS[el.element_type]}
                    </div>
                  </div>
                  <p className="col-span-2 min-w-0 text-[12px] leading-snug text-muted sm:col-span-1 sm:text-right sm:text-ink/80">
                    {el.news || STATUS_LABEL[el.status] || "Unavailable"}
                    {el.chance_of_playing_this_round != null && el.news
                      ? ""
                      : el.chance_of_playing_this_round != null
                        ? ` — ${el.chance_of_playing_this_round}% chance of playing`
                        : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </PanelCard>
      </div>
    </div>
  );
}
