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

function PricesInner() {
  const { team, boot, error, loading, session } = useSquadBootstrap();

  const rows = useMemo(() => {
    if (!team || !boot) return [];
    const byId = new Map(boot.elements.map((e) => [e.id, e]));
    const teams = new Map(boot.teams.map((t) => [t.id, t.short_name]));
    return [...team.picks]
      .sort((a, b) => a.position - b.position)
      .map((pick) => {
        const el = byId.get(pick.element);
        const now = el?.now_cost ?? pick.purchase_price;
        const delta = now - pick.purchase_price;
        return {
          id: pick.element,
          name: el?.web_name ?? `#${pick.element}`,
          team: el ? (teams.get(el.team) ?? "") : "",
          pos: ELEMENT_POS[el?.element_type ?? 3] ?? "MID",
          bought: pick.purchase_price,
          selling: pick.selling_price,
          now,
          delta,
        };
      })
      .sort((a, b) => b.delta - a.delta || a.name.localeCompare(b.name));
  }, [team, boot]);

  if (loading) return <p className="text-[12px] text-muted">Loading prices…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Price Changes</h1>
        <p className="mt-1 text-[12px] text-muted">
          {session.name} · bought vs now vs selling price
        </p>
      </div>
      <Section title="Your squad" source="my-team + bootstrap-static">
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
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-edge/70">
                  <td className="py-2 pr-3">
                    <span className="text-ink">{row.name}</span>
                    <span className="ml-1.5 text-faint">{row.team}</span>
                  </td>
                  <td className="py-2 pr-3 text-muted">{row.pos}</td>
                  <td className="tnum py-2 pr-3 text-right">{price(row.bought)}</td>
                  <td className="tnum py-2 pr-3 text-right">{price(row.now)}</td>
                  <td className="tnum py-2 pr-3 text-right">{price(row.selling)}</td>
                  <td
                    className={`tnum py-2 text-right font-medium ${
                      row.delta > 0 ? "text-actual" : row.delta < 0 ? "text-risk" : "text-muted"
                    }`}
                  >
                    {row.delta === 0 ? "—" : `${row.delta > 0 ? "+" : ""}${(row.delta / 10).toFixed(1)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function InjuriesInner() {
  const { team, boot, error, loading, session } = useSquadBootstrap();

  const rows = useMemo(() => {
    if (!team || !boot) return [];
    const byId = new Map(boot.elements.map((e) => [e.id, e]));
    const teams = new Map(boot.teams.map((t) => [t.id, t.short_name]));
    return [...team.picks]
      .map((pick) => {
        const el = byId.get(pick.element);
        if (!el) return null;
        const flagged = el.status !== "a" || Boolean(el.news) || (el.chance_of_playing_this_round != null && el.chance_of_playing_this_round < 100);
        if (!flagged) return null;
        return {
          id: el.id,
          name: el.web_name,
          team: teams.get(el.team) ?? "",
          pos: ELEMENT_POS[el.element_type] ?? "MID",
          status: el.status,
          chance: el.chance_of_playing_this_round,
          news: el.news || "—",
        };
      })
      .filter((r): r is NonNullable<typeof r> => r != null)
      .sort((a, b) => (a.chance ?? 100) - (b.chance ?? 100));
  }, [team, boot]);

  if (loading) return <p className="text-[12px] text-muted">Loading…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Injuries</h1>
        <p className="mt-1 text-[12px] text-muted">
          {session.name} · availability flags in your 15
        </p>
      </div>
      <Section title="Flagged players" source="bootstrap-static status / news">
        {rows.length === 0 ? (
          <p className="text-[12px] text-muted">No injury or availability flags in your squad.</p>
        ) : (
          <ul className="space-y-2">
            {rows.map((row) => (
              <li
                key={row.id}
                className="rounded-md border border-edge bg-raised/30 px-3 py-2.5"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-[13px] font-medium text-ink">
                    {row.name}
                    <span className="ml-2 text-[11px] text-faint">
                      {row.team} · {row.pos}
                    </span>
                  </span>
                  <span className="text-[11px] text-risk">
                    {STATUS_LABEL[row.status] ?? row.status}
                    {row.chance != null ? ` · ${row.chance}%` : ""}
                  </span>
                </div>
                <p className="mt-1 text-[12px] text-muted">{row.news}</p>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
