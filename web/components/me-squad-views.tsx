"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { MeGate } from "./me-gate";
import { Section } from "./ui/section";
import {
  accountJson,
  type BootstrapStatic,
  type MyTeam,
} from "@/lib/fpl-account";
import { fplFetch } from "@/lib/fpl-entry";
import { price } from "@/lib/format";
import { ELEMENT_POS } from "@/lib/fpl-rules";
import { useSession } from "@/lib/use-session";

const STATUS_LABEL: Record<string, string> = {
  a: "Available",
  d: "Doubtful",
  i: "Injured",
  s: "Suspended",
  u: "Unavailable",
  n: "Not available",
};

export function MePricesPage() {
  return (
    <MeGate>
      <PricesInner />
    </MeGate>
  );
}

export function MeInjuriesPage() {
  return (
    <MeGate>
      <InjuriesInner />
    </MeGate>
  );
}

function useSquadBootstrap() {
  const session = useSession();
  const [team, setTeam] = useState<MyTeam | null>(null);
  const [boot, setBoot] = useState<BootstrapStatic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!session.loggedIn) return;
    setLoading(true);
    setError(null);
    const [teamRes, bootRes] = await Promise.all([
      accountJson<MyTeam>("/api/account/team"),
      fplFetch<BootstrapStatic>("bootstrap-static"),
    ]);
    setLoading(false);
    if (!teamRes.ok) {
      setError(teamRes.error);
      return;
    }
    setTeam(teamRes.data);
    if (bootRes.ok) setBoot(bootRes.data);
  }, [session.loggedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  return { team, boot, error, loading, load, session };
}

type ViewScope = "team" | "league";

function SegmentToggle<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: readonly { id: T; label: string }[];
}) {
  return (
    <div className="flex rounded-md border border-edge p-0.5">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onChange(opt.id)}
          className={`rounded px-2.5 py-1.5 text-[12px] ${
            value === opt.id ? "bg-raised text-ink" : "text-muted hover:text-ink"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

const SCOPE_OPTIONS = [
  { id: "team" as const, label: "Your team" },
  { id: "league" as const, label: "All of FPL" },
];

const LEAGUE_PRICE_CAP = 20;

type PriceSort = "gain" | "loss";

type SquadPriceRow = {
  id: number;
  name: string;
  team: string;
  pos: string;
  bought: number;
  selling: number;
  now: number;
  delta: number;
};

type LeaguePriceRow = {
  id: number;
  name: string;
  team: string;
  pos: string;
  now: number;
  owned: string;
  delta: number;
};

function formatPriceDelta(delta: number) {
  if (delta === 0) return "—";
  return `${delta > 0 ? "+" : ""}${(delta / 10).toFixed(1)}`;
}

function deltaClass(delta: number) {
  return delta > 0 ? "text-actual" : delta < 0 ? "text-risk" : "text-muted";
}

function PricesInner() {
  const { team, boot, error, loading, session } = useSquadBootstrap();
  const [scope, setScope] = useState<ViewScope>("team");
  const [sort, setSort] = useState<PriceSort>("gain");
  const [showAllLeague, setShowAllLeague] = useState(false);

  const { squadRows, leagueRows } = useMemo(() => {
    if (!boot) {
      return { squadRows: [] as SquadPriceRow[], leagueRows: [] as LeaguePriceRow[] };
    }
    const byId = new Map(boot.elements.map((e) => [e.id, e]));
    const teams = new Map(boot.teams.map((t) => [t.id, t.short_name]));
    const squadIds = new Set((team?.picks ?? []).map((p) => p.element));

    const squadRows = (team?.picks ?? []).map((pick) => {
      const el = byId.get(pick.element);
      const now = el?.now_cost ?? pick.purchase_price;
      return {
        id: pick.element,
        name: el?.web_name ?? `#${pick.element}`,
        team: el ? (teams.get(el.team) ?? "") : "",
        pos: ELEMENT_POS[el?.element_type ?? 3] ?? "MID",
        bought: pick.purchase_price,
        selling: pick.selling_price,
        now,
        delta: now - pick.purchase_price,
      };
    });

    const leagueRows = boot.elements
      .filter((el) => !squadIds.has(el.id) && (el.cost_change_event ?? 0) !== 0)
      .map((el) => ({
        id: el.id,
        name: el.web_name,
        team: teams.get(el.team) ?? "",
        pos: ELEMENT_POS[el.element_type] ?? "MID",
        now: el.now_cost,
        owned: el.selected_by_percent,
        delta: el.cost_change_event ?? 0,
      }));

    return { squadRows, leagueRows };
  }, [team, boot]);

  const sortedSquad = useMemo(() => {
    const dir = sort === "gain" ? 1 : -1;
    return [...squadRows].sort(
      (a, b) => dir * (b.delta - a.delta) || a.name.localeCompare(b.name),
    );
  }, [squadRows, sort]);

  const sortedLeague = useMemo(() => {
    const dir = sort === "gain" ? 1 : -1;
    return [...leagueRows].sort(
      (a, b) => dir * (b.delta - a.delta) || a.name.localeCompare(b.name),
    );
  }, [leagueRows, sort]);

  const leagueCapped = sortedLeague.length > LEAGUE_PRICE_CAP;
  const visibleLeague = showAllLeague
    ? sortedLeague
    : sortedLeague.slice(0, LEAGUE_PRICE_CAP);

  if (loading) return <p className="text-[12px] text-muted">Loading prices…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Price Changes</h1>
          <p className="mt-1 text-[12px] text-muted">
            {session.name} ·{" "}
            {scope === "team" ? "P&L vs bought price" : "official movers this GW"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentToggle value={scope} onChange={setScope} options={SCOPE_OPTIONS} />
          <SegmentToggle
            value={sort}
            onChange={setSort}
            options={[
              { id: "gain", label: "Most gain" },
              { id: "loss", label: "Most loss" },
            ]}
          />
        </div>
      </div>

      {scope === "team" ? (
        <Section title="Your team" source="my-team + bootstrap-static">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead className="label-xs text-faint">
                <tr>
                  <th className="pb-2 pr-3 font-normal">Player</th>
                  <th className="pb-2 pr-3 font-normal">Pos</th>
                  <th className="pb-2 pr-3 text-right font-normal">Bought</th>
                  <th className="pb-2 pr-3 text-right font-normal">Now</th>
                  <th className="pb-2 pr-3 text-right font-normal">Sell</th>
                  <th className="pb-2 text-right font-normal">Δ</th>
                </tr>
              </thead>
              <tbody>
                {sortedSquad.map((row) => (
                  <tr key={row.id} className="border-t border-edge/70">
                    <td className="py-2 pr-3">
                      <span className="text-ink">{row.name}</span>
                      <span className="ml-1.5 text-faint">{row.team}</span>
                    </td>
                    <td className="py-2 pr-3 text-muted">{row.pos}</td>
                    <td className="tnum py-2 pr-3 text-right">{price(row.bought)}</td>
                    <td className="tnum py-2 pr-3 text-right">{price(row.now)}</td>
                    <td className="tnum py-2 pr-3 text-right">{price(row.selling)}</td>
                    <td className={`tnum py-2 text-right font-medium ${deltaClass(row.delta)}`}>
                      {formatPriceDelta(row.delta)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      ) : (
        <Section title="All of FPL" source="bootstrap-static cost_change_event">
          {leagueCapped ? (
            <p className="mb-3 text-[12px] text-muted">
              {showAllLeague
                ? `Showing all ${sortedLeague.length} movers this GW.`
                : `Showing top ${LEAGUE_PRICE_CAP} of ${sortedLeague.length} movers this GW.`}{" "}
              <button
                type="button"
                onClick={() => setShowAllLeague((v) => !v)}
                className="text-model hover:underline"
              >
                {showAllLeague ? "Show top 20" : "Show all"}
              </button>
            </p>
          ) : null}
          {visibleLeague.length === 0 ? (
            <p className="text-[12px] text-muted">No league price movers this gameweek yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12.5px]">
                <thead className="label-xs text-faint">
                  <tr>
                    <th className="pb-2 pr-3 font-normal">Player</th>
                    <th className="pb-2 pr-3 font-normal">Pos</th>
                    <th className="pb-2 pr-3 text-right font-normal">Now</th>
                    <th className="pb-2 pr-3 text-right font-normal">Owned</th>
                    <th className="pb-2 text-right font-normal">Δ GW</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleLeague.map((row) => (
                    <tr key={row.id} className="border-t border-edge/70">
                      <td className="py-2 pr-3">
                        <span className="text-ink">{row.name}</span>
                        <span className="ml-1.5 text-faint">{row.team}</span>
                      </td>
                      <td className="py-2 pr-3 text-muted">{row.pos}</td>
                      <td className="tnum py-2 pr-3 text-right">{price(row.now)}</td>
                      <td className="tnum py-2 pr-3 text-right text-muted">{row.owned}%</td>
                      <td className={`tnum py-2 text-right font-medium ${deltaClass(row.delta)}`}>
                        {formatPriceDelta(row.delta)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

type InjuryRow = {
  id: number;
  name: string;
  team: string;
  pos: string;
  status: string;
  chance: number | null;
  news: string;
  owned: number;
  ownedLabel: string;
};

function isFlagged(el: {
  status: string;
  news: string;
  chance_of_playing_this_round: number | null;
}) {
  return (
    el.status !== "a" ||
    Boolean(el.news) ||
    (el.chance_of_playing_this_round != null && el.chance_of_playing_this_round < 100)
  );
}

function ownedPct(raw: string | undefined) {
  const n = Number.parseFloat(raw ?? "");
  return Number.isFinite(n) ? n : 0;
}

function toInjuryRow(
  el: {
    id: number;
    web_name: string;
    team: number;
    element_type: number;
    status: string;
    news: string;
    chance_of_playing_this_round: number | null;
    selected_by_percent: string;
  },
  teams: Map<number, string>,
): InjuryRow {
  return {
    id: el.id,
    name: el.web_name,
    team: teams.get(el.team) ?? "",
    pos: ELEMENT_POS[el.element_type] ?? "MID",
    status: el.status,
    chance: el.chance_of_playing_this_round,
    news: el.news || "—",
    owned: ownedPct(el.selected_by_percent),
    ownedLabel: el.selected_by_percent,
  };
}

function byOwnershipDesc(a: InjuryRow, b: InjuryRow) {
  return b.owned - a.owned || (a.chance ?? 100) - (b.chance ?? 100) || a.name.localeCompare(b.name);
}

function InjuryList({ rows, empty }: { rows: InjuryRow[]; empty: string }) {
  if (rows.length === 0) {
    return <p className="text-[12px] text-muted">{empty}</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.id} className="rounded-md border border-edge bg-raised/30 px-3 py-2.5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-[13px] font-medium text-ink">
              {row.name}
              <span className="ml-2 text-[11px] text-faint">
                {row.team} · {row.pos}
              </span>
            </span>
            <span className="flex flex-wrap items-baseline gap-x-2 text-[11px]">
              <span className="tnum text-muted">{row.ownedLabel}% owned</span>
              <span className="text-risk">
                {STATUS_LABEL[row.status] ?? row.status}
                {row.chance != null ? ` · ${row.chance}%` : ""}
              </span>
            </span>
          </div>
          <p className="mt-1 text-[12px] text-muted">{row.news}</p>
        </li>
      ))}
    </ul>
  );
}

const LEAGUE_INJURY_CAP = 20;

function InjuriesInner() {
  const { team, boot, error, loading, session } = useSquadBootstrap();
  const [scope, setScope] = useState<ViewScope>("team");
  const [showAllLeague, setShowAllLeague] = useState(false);

  const { squadRows, leagueRows } = useMemo(() => {
    if (!boot) return { squadRows: [] as InjuryRow[], leagueRows: [] as InjuryRow[] };
    const teams = new Map(boot.teams.map((t) => [t.id, t.short_name]));
    const squadIds = new Set((team?.picks ?? []).map((p) => p.element));

    const squadRows = (team?.picks ?? [])
      .map((pick) => boot.elements.find((e) => e.id === pick.element))
      .filter((el): el is NonNullable<typeof el> => el != null && isFlagged(el))
      .map((el) => toInjuryRow(el, teams))
      .sort(byOwnershipDesc);

    const leagueRows = boot.elements
      .filter((el) => isFlagged(el) && !squadIds.has(el.id))
      .map((el) => toInjuryRow(el, teams))
      .sort(byOwnershipDesc);

    return { squadRows, leagueRows };
  }, [team, boot]);

  const leagueCapped = leagueRows.length > LEAGUE_INJURY_CAP;
  const visibleLeagueRows = showAllLeague
    ? leagueRows
    : leagueRows.slice(0, LEAGUE_INJURY_CAP);

  if (loading) return <p className="text-[12px] text-muted">Loading…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Injuries</h1>
          <p className="mt-1 text-[12px] text-muted">
            {session.name} · availability flags
            {scope === "league" ? ", sorted by ownership" : " in your squad"}
          </p>
        </div>
        <SegmentToggle value={scope} onChange={setScope} options={SCOPE_OPTIONS} />
      </div>

      {scope === "team" ? (
        <Section title="Your team" source="my-team + bootstrap-static">
          <InjuryList
            rows={squadRows}
            empty="No injury or availability flags in your squad."
          />
        </Section>
      ) : (
        <Section title="All of FPL" source="bootstrap-static status / news">
          {leagueCapped ? (
            <p className="mb-3 text-[12px] text-muted">
              {showAllLeague
                ? `Showing all ${leagueRows.length} by ownership.`
                : `Showing top ${LEAGUE_INJURY_CAP} of ${leagueRows.length} by ownership.`}{" "}
              <button
                type="button"
                onClick={() => setShowAllLeague((v) => !v)}
                className="text-model hover:underline"
              >
                {showAllLeague ? "Show top 20" : "Show all"}
              </button>
            </p>
          ) : null}
          <InjuryList
            rows={visibleLeagueRows}
            empty="No league-wide availability flags right now."
          />
        </Section>
      )}
    </div>
  );
}
