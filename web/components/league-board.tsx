"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Section } from "./ui/section";
import { accountJson } from "@/lib/fpl-account";
import { fplFetch, type FplEntry, type FplLeague } from "@/lib/fpl-entry";
import { loadTracked } from "@/lib/tracked-teams";
import { useSession } from "@/lib/use-session";

function rankDelta(rank: number | null | undefined, last: number | null | undefined) {
  if (rank == null || last == null || last === 0) return null;
  return last - rank;
}

function LeagueCards({
  title,
  leagues,
  kind,
  loggedIn,
  onLeave,
}: {
  title: string;
  leagues: FplLeague[];
  kind: "classic" | "h2h";
  loggedIn: boolean;
  onLeave: (id: number, kind: "classic" | "h2h") => void;
}) {
  if (leagues.length === 0) return null;
  return (
    <Section title={title}>
      <ul className="space-y-2">
        {leagues.map((league) => {
          const rank = league.entry_rank ?? league.rank ?? null;
          const delta = rankDelta(rank, league.entry_last_rank);
          const system = league.league_type === "s";
          return (
            <li
              key={league.id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-edge bg-raised/30 px-3 py-2.5"
            >
              <div className="min-w-0 flex-1">
                <Link
                  href={`/me/leagues/${league.id}?kind=${kind}`}
                  className="truncate text-[13px] font-medium text-ink hover:text-model"
                >
                  {league.name}
                </Link>
                <div className="tnum text-[11px] text-muted">
                  {system ? "Overall / system" : kind === "h2h" ? "Head to head" : "Classic"}
                </div>
              </div>
              <div className="tnum text-right">
                <div className="text-[15px] font-semibold">{rank ?? "—"}</div>
                {delta != null && delta !== 0 && (
                  <div className={`text-[11px] ${delta > 0 ? "text-actual" : "text-risk"}`}>
                    {delta > 0 ? `↑${delta}` : `↓${Math.abs(delta)}`}
                  </div>
                )}
              </div>
              {loggedIn && league.entry_can_leave && !system && (
                <button
                  type="button"
                  onClick={() => onLeave(league.id, kind)}
                  className="text-[11px] text-muted hover:text-risk"
                >
                  Leave
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}

export function LeagueBoard() {
  const session = useSession();
  const [entryId, setEntryId] = useState<number | null>(null);
  const [entry, setEntry] = useState<FplEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [kind, setKind] = useState<"classic" | "h2h">("classic");
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [leave, setLeave] = useState<{ id: number; kind: "classic" | "h2h" } | null>(null);

  useEffect(() => {
    if (session.loading) return;
    if (session.entryId) {
      setEntryId(session.entryId);
      return;
    }
    const tracked = loadTracked();
    setEntryId(tracked.compareId ?? tracked.mine[0] ?? null);
  }, [session.loading, session.entryId]);

  async function load(id: number) {
    setError(null);
    const res = await fplFetch<FplEntry>(`entry/${id}`);
    if (!res.ok) {
      setError(`Could not load entry ${id}`);
      return;
    }
    setEntry(res.data);
  }

  useEffect(() => {
    if (entryId) void load(entryId);
  }, [entryId]);

  async function join(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await accountJson("/api/account/leagues", {
      method: "POST",
      body: JSON.stringify({ action: "join", kind, code }),
    });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setCode("");
    setNotice("Joined league");
    if (entryId) void load(entryId);
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await accountJson("/api/account/leagues", {
      method: "POST",
      body: JSON.stringify({
        action: "create",
        kind,
        name: newName,
        startEvent: entry?.current_event ?? 1,
      }),
    });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setNewName("");
    setNotice("League created");
    if (entryId) void load(entryId);
  }

  async function confirmLeave() {
    if (!leave) return;
    setBusy(true);
    setError(null);
    const result = await accountJson("/api/account/leagues", {
      method: "POST",
      body: JSON.stringify({ action: "leave", kind: leave.kind, leagueId: leave.id }),
    });
    setBusy(false);
    setLeave(null);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setNotice("Left league");
    if (entryId) void load(entryId);
  }

  if (session.loading) {
    return <p className="text-[12px] text-muted">Loading…</p>;
  }

  if (!entryId) {
    return (
      <p className="text-[13px] text-muted">
        Sign in on <Link href="/me" className="text-model">My team</Link> or mark an entry as Mine
        on <Link href="/teams" className="text-model">Teams</Link> to see your leagues.
      </p>
    );
  }

  const classic = entry?.leagues?.classic ?? [];
  const h2h = entry?.leagues?.h2h ?? [];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Leagues</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          {entry?.name ?? `Entry ${entryId}`}
          {entry?.summary_overall_rank != null
            ? ` · overall rank ${entry.summary_overall_rank.toLocaleString()}`
            : ""}
        </p>
      </div>

      {notice && <p className="text-[12px] text-actual">{notice}</p>}
      {error && <p className="text-[12px] text-risk">{error}</p>}

      <LeagueCards
        title="Classic"
        leagues={classic}
        kind="classic"
        loggedIn={session.loggedIn}
        onLeave={(id, k) => setLeave({ id, kind: k })}
      />
      <LeagueCards
        title="Head to head"
        leagues={h2h}
        kind="h2h"
        loggedIn={session.loggedIn}
        onLeave={(id, k) => setLeave({ id, kind: k })}
      />

      {session.loggedIn && (
        <Section
          title="Join or create"
          subtitle="Writes go to FPL with your session. Leave is not undoable."
        >
          <div className="flex gap-2 text-[12px]">
            <button
              type="button"
              onClick={() => setKind("classic")}
              className={`rounded-md px-2.5 py-1 ${kind === "classic" ? "bg-raised text-ink" : "text-muted"}`}
            >
              Classic
            </button>
            <button
              type="button"
              onClick={() => setKind("h2h")}
              className={`rounded-md px-2.5 py-1 ${kind === "h2h" ? "bg-raised text-ink" : "text-muted"}`}
            >
              H2H
            </button>
          </div>
          <form onSubmit={join} className="mt-4 flex flex-wrap gap-2">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Invite code"
              className="w-44 rounded-md border border-edge bg-raised px-2.5 py-1.5 font-mono text-[12px] outline-none focus:border-edge-bright"
            />
            <button
              type="submit"
              disabled={busy || !code.trim()}
              className="rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model disabled:opacity-40"
            >
              Join
            </button>
          </form>
          <form onSubmit={create} className="mt-3 flex flex-wrap gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New league name"
              className="w-56 rounded-md border border-edge bg-raised px-2.5 py-1.5 text-[12px] outline-none focus:border-edge-bright"
            />
            <button
              type="submit"
              disabled={busy || !newName.trim()}
              className="rounded-md border border-edge px-3 py-1.5 text-[12px] disabled:opacity-40"
            >
              Create
            </button>
          </form>
        </Section>
      )}

      {leave && (
        <div className="panel p-4">
          <p className="text-[13px]">Leave this league?</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void confirmLeave()}
              className="rounded-md bg-risk/15 px-3 py-1.5 text-[12px] text-risk"
            >
              Leave
            </button>
            <button
              type="button"
              onClick={() => setLeave(null)}
              className="rounded-md px-3 py-1.5 text-[12px] text-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
