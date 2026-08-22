"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Section } from "./ui/section";
import { fplFetch, type FplEntry } from "@/lib/fpl-entry";
import { loadTracked } from "@/lib/tracked-teams";
import { useSession } from "@/lib/use-session";

type StandingRow = {
  id: number;
  event_total: number;
  player_name: string;
  rank: number | null;
  last_rank: number | null;
  total: number;
  entry: number;
  entry_name: string;
};

type StandingsPayload = {
  league?: {
    id: number;
    name: string;
    league_type?: string;
    scoring?: string;
  };
  standings?: {
    has_next: boolean;
    page: number;
    results: StandingRow[];
  };
};

export function LeagueStandings({
  leagueId,
  kind,
}: {
  leagueId: number;
  kind: "classic" | "h2h";
}) {
  const session = useSession();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<StandingsPayload | null>(null);
  const [mine, setMine] = useState<number | null>(null);
  const [myRank, setMyRank] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session.loading) return;
    const tracked = loadTracked();
    setMine(session.entryId ?? tracked.compareId ?? tracked.mine[0] ?? null);
  }, [session.loading, session.entryId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      const path =
        kind === "h2h"
          ? `leagues-h2h/${leagueId}/standings?page_standings=${page}`
          : `leagues-classic/${leagueId}/standings?page_standings=${page}`;
      const res = await fplFetch<StandingsPayload>(path);
      if (cancelled) return;
      if (!res.ok) {
        setError("Could not load standings");
        return;
      }
      setData(res.data);
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, kind, page]);

  useEffect(() => {
    if (!mine) return;
    let cancelled = false;
    (async () => {
      const res = await fplFetch<FplEntry>(`entry/${mine}`);
      if (cancelled || !res.ok) return;
      const leagues = [...(res.data.leagues?.classic ?? []), ...(res.data.leagues?.h2h ?? [])];
      const row = leagues.find((l) => l.id === leagueId);
      setMyRank(row?.entry_rank ?? row?.rank ?? null);
    })();
    return () => {
      cancelled = true;
    };
  }, [mine, leagueId]);

  const system = data?.league?.league_type === "s";
  const rows = data?.standings?.results ?? [];
  const highlighted = useMemo(() => new Set(mine == null ? [] : [mine]), [mine]);

  if (error) return <p className="text-[13px] text-risk">{error}</p>;
  if (!data) return <p className="text-[12px] text-muted">Loading standings…</p>;

  return (
    <div className="space-y-5">
      <div>
        <Link href="/leagues" className="text-[11px] text-muted hover:text-ink">
          ← Leagues
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">
          {data.league?.name ?? `League ${leagueId}`}
        </h1>
        {myRank != null && (
          <p className="mt-1 text-[12px] text-muted">
            Your rank <span className="tnum text-ink">{myRank.toLocaleString()}</span>
          </p>
        )}
      </div>

      {system ? (
        <Section
          title="System league"
          subtitle="Overall and country leagues are too large to page here. Your rank is on the card above."
        >
          <p className="text-[12px] text-muted">Open a private classic or H2H league for a table.</p>
        </Section>
      ) : (
        <Section title="Standings" source={`fantasy.premierleague.com/api/leagues-${kind}/{id}/standings/`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead className="label-xs text-faint">
                <tr>
                  <th className="pb-2 pr-3 font-normal">Rank</th>
                  <th className="pb-2 pr-3 font-normal">Team</th>
                  <th className="pb-2 pr-3 font-normal">Manager</th>
                  <th className="pb-2 pr-3 text-right font-normal">GW</th>
                  <th className="pb-2 text-right font-normal">Total</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const delta =
                    row.rank != null && row.last_rank != null && row.last_rank !== 0
                      ? row.last_rank - row.rank
                      : null;
                  const mineRow = highlighted.has(row.entry);
                  return (
                    <tr
                      key={row.id}
                      className={`border-t border-edge/70 ${mineRow ? "bg-model/8" : ""}`}
                    >
                      <td className="tnum py-2 pr-3">
                        {row.rank ?? "—"}
                        {delta != null && delta !== 0 && (
                          <span className={`ml-1.5 text-[10px] ${delta > 0 ? "text-actual" : "text-risk"}`}>
                            {delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`}
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <Link href={`/teams/${row.entry}`} className="hover:text-model">
                          {row.entry_name}
                        </Link>
                      </td>
                      <td className="py-2 pr-3 text-muted">{row.player_name}</td>
                      <td className="tnum py-2 pr-3 text-right">{row.event_total}</td>
                      <td className="tnum py-2 text-right font-medium">{row.total}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center gap-3 text-[12px]">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="text-muted disabled:opacity-30 hover:text-ink"
            >
              Previous
            </button>
            <span className="tnum text-faint">Page {data.standings?.page ?? page}</span>
            <button
              type="button"
              disabled={!data.standings?.has_next}
              onClick={() => setPage((p) => p + 1)}
              className="text-muted disabled:opacity-30 hover:text-ink"
            >
              Next
            </button>
          </div>
        </Section>
      )}
    </div>
  );
}
