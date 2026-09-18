"use client";

import { Section } from "./ui/section";
import { accountJson, type BootstrapStatic } from "@/lib/fpl-account";
import { fplFetch } from "@/lib/fpl-entry";
import { price } from "@/lib/format";
import {
  BANK_MENU_M,
  type PrefsPayload,
  type PrefsResult,
  type SquadViewJson,
} from "@/lib/prefs";
import type { ComparePoolPlayer } from "@/lib/team-compare";
import { useEffect, useMemo, useState } from "react";

function SquadCard({
  title,
  note,
  squad,
}: {
  title: string;
  note?: string;
  squad: SquadViewJson;
}) {
  return (
    <div className="rounded-lg border border-edge bg-panel/40 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[14px] font-semibold tracking-tight">{title}</h3>
        <span className="tnum text-[13px] text-muted">
          U {squad.u.toFixed(2)} · XI+C μ {squad.next_xi_mu.toFixed(1)} · bank{" "}
          {price(squad.bank)}
        </span>
      </div>
      {note ? <p className="mt-1 text-[12px] text-muted">{note}</p> : null}
      <p className="mt-3 text-[12px] text-ink">
        <span className="text-faint">C</span> {squad.captain}{" "}
        <span className="text-faint">VC</span> {squad.vice}
      </p>
      <p className="mt-2 text-[12px] leading-relaxed text-ink/90">
        <span className="text-faint">XI</span> {squad.xi.join(", ")}
      </p>
      <p className="mt-1 text-[12px] leading-relaxed text-muted">
        <span className="text-faint">Bench</span> {squad.bench.join(", ")}
      </p>
      <p className="mt-2 text-[11px] text-faint">
        club max {squad.club_max} · minutes-risk count {squad.minutes_risk}{" "}
        (descriptive only)
      </p>
    </div>
  );
}

export function PreferenceSolve({ pool }: { pool: ComparePoolPlayer[] }) {
  const [lock, setLock] = useState<number[]>([]);
  const [ban, setBan] = useState<number[]>([]);
  const [bank, setBank] = useState<number | null>(null);
  const [clubMax, setClubMax] = useState<Record<number, number>>({});
  const [query, setQuery] = useState("");
  const [teams, setTeams] = useState<{ id: number; name: string; short: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PrefsResult | null>(null);

  useEffect(() => {
    void (async () => {
      const boot = await fplFetch<BootstrapStatic>("bootstrap-static");
      if (!boot.ok) return;
      setTeams(
        (boot.data.teams ?? []).map((t) => ({
          id: t.id,
          name: t.name,
          short: t.short_name,
        })),
      );
    })();
  }, []);

  const byId = useMemo(() => new Map(pool.map((p) => [p.id, p])), [pool]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    return pool
      .filter((p) => p.name.toLowerCase().includes(q))
      .slice(0, 12);
  }, [pool, query]);

  function toggle(list: number[], id: number, set: (v: number[]) => void) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  async function run() {
    setLoading(true);
    setError(null);
    const payload: PrefsPayload = {
      lock,
      ban,
      min_bank_m: bank,
      club_max: Object.fromEntries(
        Object.entries(clubMax)
          .filter(([, v]) => v < 3)
          .map(([k, v]) => [k, v]),
      ),
    };
    const res = await accountJson<PrefsResult>("/api/account/prefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setLoading(false);
    if (!res.ok) {
      setError(res.error);
      setResult(null);
      return;
    }
    setResult(res.data);
  }

  return (
    <div className="space-y-6">
      <Section
        title="Model A under your constraints"
        source="engine.preferences · same U; feasible set only"
      >
        <p className="max-w-2xl text-[13px] leading-relaxed text-muted">
          Best greenfield squad for Model A, then the best squad{" "}
          <span className="text-ink">given your stated constraints</span>. Not
          robust / flexible / upside — no second objective.
        </p>

        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div>
              <label className="label-xs text-muted">Find player (LOCK / BAN)</label>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a name…"
                className="mt-1.5 w-full rounded-md border border-edge bg-void/40 px-3 py-2 text-[13px]"
              />
              {matches.length > 0 ? (
                <ul className="mt-2 max-h-40 overflow-y-auto rounded-md border border-edge divide-y divide-edge">
                  {matches.map((p) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between gap-2 px-3 py-1.5 text-[12px]"
                    >
                      <span>
                        {p.name}{" "}
                        <span className="text-faint">
                          {p.pos} · #{p.id}
                        </span>
                      </span>
                      <span className="flex gap-1">
                        <button
                          type="button"
                          className="rounded border border-edge px-2 py-0.5 hover:border-model"
                          onClick={() => {
                            toggle(lock, p.id, setLock);
                            setBan((b) => b.filter((x) => x !== p.id));
                          }}
                        >
                          Lock
                        </button>
                        <button
                          type="button"
                          className="rounded border border-edge px-2 py-0.5 hover:border-risk"
                          onClick={() => {
                            toggle(ban, p.id, setBan);
                            setLock((l) => l.filter((x) => x !== p.id));
                          }}
                        >
                          Ban
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {(lock.length > 0 || ban.length > 0) && (
                <div className="mt-2 flex flex-wrap gap-2 text-[12px]">
                  {lock.map((id) => (
                    <button
                      key={`l${id}`}
                      type="button"
                      className="rounded-full border border-model/40 bg-model/10 px-2.5 py-0.5"
                      onClick={() => setLock((l) => l.filter((x) => x !== id))}
                    >
                      Lock {byId.get(id)?.name ?? id} ×
                    </button>
                  ))}
                  {ban.map((id) => (
                    <button
                      key={`b${id}`}
                      type="button"
                      className="rounded-full border border-risk/40 bg-risk/10 px-2.5 py-0.5"
                      onClick={() => setBan((b) => b.filter((x) => x !== id))}
                    >
                      Ban {byId.get(id)?.name ?? id} ×
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="label-xs text-muted">Min bank (ITB)</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setBank(null)}
                  className={`rounded-full border px-3 py-1 text-[12px] ${
                    bank == null ? "border-model bg-model/15" : "border-edge"
                  }`}
                >
                  None
                </button>
                {BANK_MENU_M.filter((m) => m > 0).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setBank(m)}
                    className={`rounded-full border px-3 py-1 text-[12px] ${
                      bank === m ? "border-model bg-model/15" : "border-edge"
                    }`}
                  >
                    £{m.toFixed(1)}m
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="label-xs text-muted">Club max (default 3)</div>
              <div className="mt-2 max-h-48 space-y-1 overflow-y-auto text-[12px]">
                {teams.map((t) => (
                  <div key={t.id} className="flex items-center justify-between gap-2">
                    <span>
                      {t.short}{" "}
                      <span className="text-faint">{t.name}</span>
                    </span>
                    <select
                      className="rounded border border-edge bg-void/40 px-2 py-1"
                      value={clubMax[t.id] ?? 3}
                      onChange={(e) => {
                        const v = Number(e.target.value);
                        setClubMax((prev) => {
                          const next = { ...prev };
                          if (v >= 3) delete next[t.id];
                          else next[t.id] = v;
                          return next;
                        });
                      }}
                    >
                      <option value={3}>3</option>
                      <option value={2}>max 2</option>
                      <option value={1}>max 1</option>
                      <option value={0}>max 0</option>
                    </select>
                  </div>
                ))}
              </div>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={() => void run()}
              className="rounded-full border border-model/50 bg-model/20 px-5 py-2.5 text-[13px] font-medium hover:bg-model/30 disabled:opacity-50"
            >
              {loading ? "Solving…" : "Solve Model A"}
            </button>
            {error ? <p className="text-[13px] text-risk">{error}</p> : null}
          </div>

          <div className="space-y-4">
            {result ? (
              <>
                <SquadCard title="Model A optimum" squad={result.s1} />
                {result.s2 ? (
                  <SquadCard
                    title="Best squad given your constraints"
                    note={
                      result.delta_u != null
                        ? `utility ${result.delta_u > 0 ? "−" : "+"}${Math.abs(result.delta_u).toFixed(2)} vs Model A · D=${result.distance}`
                        : undefined
                    }
                    squad={result.s2}
                  />
                ) : result.preferences.lock.length ||
                  result.preferences.ban.length ||
                  result.preferences.min_bank_m != null ||
                  Object.keys(result.preferences.club_max).length ? (
                  <p className="rounded-lg border border-risk/40 bg-risk/10 p-4 text-[13px] text-risk">
                    {result.message ?? "No feasible squad under these constraints"}
                  </p>
                ) : (
                  <p className="text-[13px] text-muted">
                    No preferences set — showing Model A only. Add a lock, ban, bank,
                    or club cap and solve again.
                  </p>
                )}
                {result.enters.length > 0 || result.exits.length > 0 ? (
                  <p className="text-[12px] text-muted">
                    {result.enters.length > 0 ? (
                      <>
                        In: {result.enters.join(", ")}
                        <br />
                      </>
                    ) : null}
                    {result.exits.length > 0 ? <>Out: {result.exits.join(", ")}</> : null}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="text-[13px] text-muted">
                Run a solve to compare Model A with Model A under your constraints.
              </p>
            )}
          </div>
        </div>
      </Section>
    </div>
  );
}
