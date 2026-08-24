"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LoginForm } from "./login-form";
import { ManagePitch } from "./manage-pitch";
import { Section } from "./ui/section";
import { Stat, StatRow } from "./ui/stat";
import type { CellPlayer } from "./player-cell";
import {
  accountJson,
  type BootstrapElement,
  type BootstrapStatic,
  type MyTeam,
  type MyTeamPick,
  type PendingTransfer,
} from "@/lib/fpl-account";
import { fplFetch } from "@/lib/fpl-entry";
import { dec, price } from "@/lib/format";
import {
  CHIP_LABEL,
  ELEMENT_POS,
  clubLegal,
  formationOf,
  transferHit,
  xiLegal,
} from "@/lib/fpl-rules";
import type { ComparePoolPlayer } from "@/lib/team-compare";
import type { Position } from "@/lib/types";
import { useSession } from "@/lib/use-session";

type EventRow = {
  id: number;
  name: string;
  deadline_time: string | null;
  is_current: boolean;
  is_next: boolean;
};

function ensureCaptainInXi(picks: MyTeamPick[]): MyTeamPick[] {
  const cap = picks.find((p) => p.is_captain);
  if (cap && cap.position <= 11) return picks;
  const vice = picks.find((p) => p.is_vice_captain && p.position <= 11);
  const first = [...picks]
    .filter((p) => p.position <= 11)
    .sort((a, b) => a.position - b.position)[0];
  const next = vice ?? first;
  if (!next) return picks;
  return picks.map((p) => ({
    ...p,
    is_captain: p.element === next.element,
    is_vice_captain:
      p.element === next.element ? false : cap ? p.element === cap.element : p.is_vice_captain,
  }));
}

function swapPicks(picks: MyTeamPick[], a: number, b: number): MyTeamPick[] {
  const left = picks.find((p) => p.element === a);
  const right = picks.find((p) => p.element === b);
  if (!left || !right) return picks;
  const next = picks.map((p) => {
    if (p.element === a) return { ...p, position: right.position };
    if (p.element === b) return { ...p, position: left.position };
    return p;
  });
  return ensureCaptainInXi(next);
}

function xiPositions(
  picks: MyTeamPick[],
  byElement: Map<number, { pos: Position }>,
): Position[] {
  return picks
    .filter((p) => p.position <= 11)
    .sort((a, b) => a.position - b.position)
    .map((p) => byElement.get(p.element)?.pos ?? "MID");
}

export type ManageView = "status" | "pick-team" | "transfers";

export function ManageTeam({
  pool,
  season,
  gw,
  view,
}: {
  pool: ComparePoolPlayer[];
  season: string;
  gw: number;
  view: ManageView;
}) {
  const session = useSession();
  const [team, setTeam] = useState<MyTeam | null>(null);
  const [picks, setPicks] = useState<MyTeamPick[]>([]);
  const [boot, setBoot] = useState<BootstrapStatic | null>(null);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingTransfer[]>([]);
  const [chipPlay, setChipPlay] = useState<string | null>(null);
  const [pickerFor, setPickerFor] = useState<MyTeamPick | null>(null);
  const [confirm, setConfirm] = useState<null | "transfers" | "chip" | "hit">(null);
  const [pendingChipName, setPendingChipName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem("fpl.armed-chip");
      if (stored) setChipPlay(stored);
    } catch {
      /* private mode */
    }
  }, []);

  function armChip(name: string | null) {
    setChipPlay(name);
    try {
      if (name) sessionStorage.setItem("fpl.armed-chip", name);
      else sessionStorage.removeItem("fpl.armed-chip");
    } catch {
      /* private mode */
    }
  }

  const load = useCallback(async (opts?: { keepChip?: boolean }) => {
    if (!session.loggedIn) return;
    setLoadError(null);
    const [teamRes, bootRes] = await Promise.all([
      accountJson<MyTeam>("/api/account/team"),
      fplFetch<BootstrapStatic & { events?: EventRow[] }>("bootstrap-static"),
    ]);
    if (!teamRes.ok) {
      setLoadError(teamRes.error);
      return;
    }
    setTeam(teamRes.data);
    setPicks(teamRes.data.picks ?? []);
    setPending([]);
    if (!opts?.keepChip) armChip(null);
    setSelected(null);
    if (bootRes.ok) {
      setBoot({ elements: bootRes.data.elements, teams: bootRes.data.teams });
      setEvents(bootRes.data.events ?? []);
    }
  }, [session.loggedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  const poolById = useMemo(() => new Map(pool.map((p) => [p.id, p])), [pool]);
  const elements = useMemo(
    () => new Map((boot?.elements ?? []).map((e) => [e.id, e])),
    [boot],
  );
  const teams = useMemo(
    () => new Map((boot?.teams ?? []).map((t) => [t.id, t])),
    [boot],
  );

  const byElement = useMemo(() => {
    const map = new Map<number, { pos: Position; teamId: number }>();
    for (const [id, el] of elements) {
      map.set(id, { pos: ELEMENT_POS[el.element_type] ?? "MID", teamId: el.team });
    }
    for (const p of pool) {
      if (!map.has(p.id) && p.teamId != null) {
        map.set(p.id, { pos: p.pos, teamId: p.teamId });
      }
    }
    return map;
  }, [elements, pool]);

  const nextEvent = events.find((e) => e.is_next) ?? events.find((e) => e.is_current);
  const eventId = nextEvent?.id ?? gw;

  const wcActive =
    team?.chips.some(
      (c) =>
        (c.name === "wildcard" || c.name === "freehit") &&
        (c.status_for_entry === "active" || chipPlay === c.name),
    ) ?? false;

  const bank =
    (team?.transfers.bank ?? 0) +
    pending.reduce((sum, t) => sum + t.selling_price - t.purchase_price, 0);
  const hit = wcActive
    ? 0
    : transferHit(
        team?.transfers.made ?? 0,
        team?.transfers.limit ?? 1,
        pending.length,
        team?.transfers.cost ?? 4,
      );
  const ftsLeft = wcActive
    ? Infinity
    : Math.max(0, (team?.transfers.limit ?? 1) - (team?.transfers.made ?? 0) - pending.length);

  const formationError = xiLegal(xiPositions(picks, byElement));
  const clubError = clubLegal(
    picks.map((p) => byElement.get(p.element)?.teamId).filter((id): id is number => id != null),
  );

  const lineupDirty = useMemo(() => {
    if (!team) return false;
    const key = (p: MyTeamPick) =>
      `${p.element}:${p.position}:${p.is_captain ? 1 : 0}:${p.is_vice_captain ? 1 : 0}`;
    const a = [...team.picks].map(key).sort().join("|");
    const b = [...picks].map(key).sort().join("|");
    return a !== b;
  }, [team, picks]);

  const cells = useMemo(() => {
    const toCell = (pick: MyTeamPick): CellPlayer => {
      const el = elements.get(pick.element);
      const pooled = poolById.get(pick.element);
      const pos = (ELEMENT_POS[el?.element_type ?? 3] ?? pooled?.pos ?? "MID") as Position;
      const teamId = el?.team ?? pooled?.teamId ?? null;
      return {
        id: pick.element,
        name: pooled?.name ?? el?.web_name ?? `#${pick.element}`,
        pos,
        teamCode: pooled?.teamCode ?? (teamId != null ? (teams.get(teamId)?.short_name ?? null) : null),
        teamId,
        cost: pick.selling_price ?? el?.now_cost ?? pooled?.cost ?? null,
        mu: pooled?.mu ?? null,
        sigma: pooled?.sigma ?? null,
        pStart: pooled?.pStart ?? null,
        p10: null,
        pts: null,
        mins: null,
        captain: pick.is_captain,
        vice: pick.is_vice_captain && !pick.is_captain,
        status: el?.status ?? null,
        news: el?.news || null,
      };
    };
    const sorted = [...picks].sort((a, b) => a.position - b.position);
    return {
      xi: sorted.filter((p) => p.position <= 11).map(toCell),
      bench: sorted.filter((p) => p.position > 11).map(toCell),
    };
  }, [picks, elements, poolById, teams]);

  const selectedPick = picks.find((p) => p.element === selected) ?? null;
  const xiPos = xiPositions(picks, byElement);
  const formation = formationOf(xiPos);

  function onSelect(id: number) {
    setError(null);
    if (selected == null) {
      setSelected(id);
      return;
    }
    if (selected === id) {
      setSelected(null);
      return;
    }
    const next = swapPicks(picks, selected, id);
    const err = xiLegal(xiPositions(next, byElement));
    if (err) {
      setError(err);
      setSelected(null);
      return;
    }
    setPicks(next);
    setSelected(null);
  }

  function setCaptain(id: number) {
    const pick = picks.find((p) => p.element === id);
    if (!pick || pick.position > 11) {
      setError("Captain must start");
      return;
    }
    setPicks(
      picks.map((p) => ({
        ...p,
        is_captain: p.element === id,
        is_vice_captain: p.element === id ? false : p.is_vice_captain,
      })),
    );
  }

  function setVice(id: number) {
    const pick = picks.find((p) => p.element === id);
    if (!pick || pick.position > 11) {
      setError("Vice-captain must start");
      return;
    }
    const next = picks.map((p) => ({
      ...p,
      is_vice_captain: p.element === id,
      is_captain: p.element === id ? false : p.is_captain,
    }));
    if (!next.some((p) => p.is_captain && p.position <= 11)) {
      setError("Pick a captain too");
    }
    setPicks(next);
  }

  function applyTransfer(incoming: BootstrapElement) {
    if (!pickerFor) return;
    const outgoing = pickerFor;
    if (incoming.element_type !== (elements.get(outgoing.element)?.element_type ?? 0)) {
      setError("Replacement must be the same position");
      return;
    }
    if (picks.some((p) => p.element === incoming.id)) {
      setError("Already in the squad");
      return;
    }
    const nextPicks = picks.map((p) =>
      p.element === outgoing.element
        ? {
            ...p,
            element: incoming.id,
            purchase_price: incoming.now_cost,
            selling_price: incoming.now_cost,
          }
        : p,
    );
    const teamIds = nextPicks
      .map((p) => {
        if (p.element === incoming.id) return incoming.team;
        return byElement.get(p.element)?.teamId;
      })
      .filter((id): id is number => id != null);
    const clubs = clubLegal(teamIds);
    if (clubs) {
      setError(clubs);
      return;
    }
    const nextBank = bank + outgoing.selling_price - incoming.now_cost;
    if (nextBank < 0) {
      setError(`Need ${price(incoming.now_cost - outgoing.selling_price)} more in the bank`);
      return;
    }
    setPending((prev) => [
      ...prev,
      {
        element_in: incoming.id,
        element_out: outgoing.element,
        purchase_price: incoming.now_cost,
        selling_price: outgoing.selling_price,
      },
    ]);
    setPicks(nextPicks);
    setPickerFor(null);
    setQuery("");
    setSelected(null);
    setError(null);
  }

  async function savePicks(chip: string | null) {
    setBusy(true);
    setError(null);
    const result = await accountJson("/api/account/picks", {
      method: "POST",
      body: JSON.stringify({
        chip,
        picks: picks.map((p) => ({
          element: p.element,
          position: p.position,
          is_captain: p.is_captain,
          is_vice_captain: p.is_vice_captain,
        })),
      }),
    });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setNotice(chip ? `${CHIP_LABEL[chip] ?? chip} saved` : "Lineup saved");
    armChip(null);
    await load();
  }

  async function saveTransfers(chip: string | null) {
    setBusy(true);
    setError(null);
    const result = await accountJson("/api/account/transfers", {
      method: "POST",
      body: JSON.stringify({
        event: eventId,
        chip,
        transfers: pending,
      }),
    });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setNotice(
      hit > 0
        ? `Transfers confirmed · −${hit} hit`
        : "Transfers confirmed",
    );
    const keepChip = chipPlay === "bboost" || chipPlay === "3xc";
    if (!keepChip) armChip(null);
    await load({ keepChip });
  }

  function requestChip(name: string) {
    setPendingChipName(name);
    setConfirm("chip");
  }

  function confirmChip() {
    if (!pendingChipName) return;
    armChip(pendingChipName);
    setConfirm(null);
    setNotice(`${CHIP_LABEL[pendingChipName] ?? pendingChipName} armed — save lineup or transfers to play it`);
  }

  function requestTransfers() {
    if (pending.length === 0) return;
    setConfirm(hit > 0 ? "hit" : "transfers");
  }

  const pickerList = useMemo(() => {
    if (!pickerFor || !boot) return [];
    const outType = elements.get(pickerFor.element)?.element_type;
    const owned = new Set(picks.map((p) => p.element));
    const q = query.trim().toLowerCase();
    return boot.elements
      .filter((e) => e.element_type === outType && !owned.has(e.id) && e.can_select !== false)
      .filter((e) => !q || e.web_name.toLowerCase().includes(q))
      .map((e) => ({ el: e, mu: poolById.get(e.id)?.mu ?? -1, pStart: poolById.get(e.id)?.pStart ?? null }))
      .sort((a, b) => b.mu - a.mu || a.el.now_cost - b.el.now_cost)
      .slice(0, 80);
  }, [pickerFor, boot, elements, picks, query, poolById]);

  void season;

  if (session.loading) {
    return <p className="text-[12px] text-muted">Checking FPL session…</p>;
  }
  if (!session.loggedIn) {
    return <LoginForm onLoggedIn={() => void session.refresh()} />;
  }
  if (loadError) {
    return (
      <div className="space-y-3">
        <p className="text-[13px] text-risk">{loadError}</p>
        <button type="button" className="text-[12px] text-model" onClick={() => void load()}>
          Retry
        </button>
      </div>
    );
  }
  if (!team) {
    return <p className="text-[12px] text-muted">Loading squad…</p>;
  }

  const transferChip =
    chipPlay === "wildcard" || chipPlay === "freehit" ? chipPlay : null;
  const picksChip =
    chipPlay === "bboost" || chipPlay === "3xc"
      ? chipPlay
      : pending.length === 0 && (chipPlay === "wildcard" || chipPlay === "freehit")
        ? chipPlay
        : null;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{session.name ?? "My team"}</h1>
        <p className="mt-1 text-[12px] text-muted">
          {session.playerName}
          {nextEvent?.deadline_time
            ? ` · deadline ${nextEvent.deadline_time.replace("T", " ").slice(0, 16)} UTC`
            : ""}
        </p>
      </div>

      {notice && <p className="text-[12px] text-actual">{notice}</p>}
      {error && <p className="text-[12px] text-risk">{error}</p>}

      {view === "status" && (
        <>
          <Section title="Bank and transfers" source="fantasy.premierleague.com/api/my-team/{id}/">
            <StatRow>
              <Stat label="Bank" value={price(bank)} />
              <Stat label="Squad value" value={price(team.transfers.value)} />
              <Stat
                label="Free transfers"
                value={wcActive ? "Unlimited" : String(Number.isFinite(ftsLeft) ? ftsLeft : 0)}
              />
              <Stat
                label="Hit"
                value={hit ? `−${hit}` : "0"}
                tone={hit ? "risk" : "actual"}
                note={`${formation} XI`}
              />
            </StatRow>
          </Section>

          <Section title="Chips" subtitle="One-shot for this half. Arm here, then save on Pick Team or Transfers.">
            <div className="flex flex-wrap gap-2">
              {(team.chips ?? []).map((chip) => {
                const available = chip.status_for_entry === "available";
                const active = chip.status_for_entry === "active" || chipPlay === chip.name;
                return (
                  <button
                    key={chip.name}
                    type="button"
                    disabled={!available && !active}
                    onClick={() => available && requestChip(chip.name)}
                    className={`rounded-full border px-3 py-1 text-[11px] ${
                      active
                        ? "border-oracle/60 bg-oracle/15 text-oracle"
                        : available
                          ? "border-edge text-ink hover:border-edge-bright"
                          : "border-edge/50 text-faint"
                    }`}
                  >
                    {CHIP_LABEL[chip.name] ?? chip.name}
                    {active ? " · on" : available ? "" : " · used"}
                  </button>
                );
              })}
            </div>
          </Section>

          <ManagePitch xi={cells.xi} bench={cells.bench} selected={null} onSelect={() => {}} />
        </>
      )}

      {view === "pick-team" && (
        <>
          {formationError && lineupDirty && (
            <p className="text-[12px] text-risk">{formationError}</p>
          )}
          <p className="text-[12px] text-muted">
            Tap two players to swap XI and bench. Captain stays in the XI. Transfers live under
            the Transfers tab.
          </p>

          <ManagePitch
            xi={cells.xi}
            bench={cells.bench}
            selected={selected}
            onSelect={onSelect}
          />

          {selectedPick && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCaptain(selectedPick.element)}
                className="rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model"
              >
                Captain
              </button>
              <button
                type="button"
                onClick={() => setVice(selectedPick.element)}
                className="rounded-md border border-edge px-3 py-1.5 text-[12px]"
              >
                Vice
              </button>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md px-3 py-1.5 text-[12px] text-muted"
              >
                Clear
              </button>
            </div>
          )}

          <button
            type="button"
            disabled={busy || Boolean(formationError) || (!lineupDirty && !picksChip)}
            onClick={() => void savePicks(picksChip)}
            className="rounded-md bg-model/15 px-4 py-2 text-[13px] text-model disabled:opacity-40"
          >
            Save lineup
          </button>
        </>
      )}

      {view === "transfers" && (
        <>
          <Section title="Budget">
            <StatRow>
              <Stat label="Bank" value={price(bank)} />
              <Stat
                label="Free transfers"
                value={wcActive ? "Unlimited" : String(Number.isFinite(ftsLeft) ? ftsLeft : 0)}
              />
              <Stat
                label="Hit"
                value={hit ? `−${hit}` : "0"}
                tone={hit ? "risk" : "actual"}
              />
            </StatRow>
          </Section>

          {clubError && <p className="text-[12px] text-risk">{clubError}</p>}
          <p className="text-[12px] text-muted">
            Tap a player, then Transfer out. Replacements are sorted by V1 μ.
          </p>

          <ManagePitch
            xi={cells.xi}
            bench={cells.bench}
            selected={selected}
            onSelect={(id) => {
              setError(null);
              setSelected((prev) => (prev === id ? null : id));
            }}
          />

          {selectedPick && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setPickerFor(selectedPick)}
                className="rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model"
              >
                Transfer out
              </button>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md px-3 py-1.5 text-[12px] text-muted"
              >
                Clear
              </button>
            </div>
          )}

          {pending.length > 0 && (
            <Section title="Pending transfers">
              <ul className="space-y-1.5 text-[12px]">
                {pending.map((t) => (
                  <li key={`${t.element_out}-${t.element_in}`} className="flex justify-between gap-3">
                    <span>
                      {elements.get(t.element_out)?.web_name ?? t.element_out}
                      <span className="text-faint"> → </span>
                      {elements.get(t.element_in)?.web_name ?? t.element_in}
                    </span>
                    <span className="tnum text-muted">
                      {price(t.purchase_price - t.selling_price)}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <button
            type="button"
            disabled={busy || pending.length === 0 || Boolean(clubError)}
            onClick={requestTransfers}
            className="rounded-md border border-edge px-4 py-2 text-[13px] disabled:opacity-40"
          >
            Confirm transfers{hit > 0 ? ` (−${hit})` : ""}
          </button>
        </>
      )}

      <Dialog.Root open={pickerFor != null} onOpenChange={(open) => !open && setPickerFor(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-void/70" />
          <Dialog.Content className="fixed inset-x-4 top-[6vh] z-50 mx-auto flex max-h-[88vh] max-w-lg flex-col overflow-hidden rounded-xl border border-edge bg-panel p-4 shadow-xl outline-none">
            <div className="mb-3 flex items-start justify-between gap-3">
              <Dialog.Title className="text-[14px] font-medium">
                Replace {pickerFor ? (elements.get(pickerFor.element)?.web_name ?? "") : ""}
              </Dialog.Title>
              <Dialog.Close className="text-[11px] text-muted hover:text-ink">Close</Dialog.Close>
            </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search"
              className="mb-3 rounded-md border border-edge bg-raised px-2.5 py-1.5 text-[13px] outline-none focus:border-edge-bright"
            />
            <ul className="min-h-0 flex-1 space-y-px overflow-y-auto">
              {pickerList.map(({ el, mu, pStart }) => (
                <li key={el.id}>
                  <button
                    type="button"
                    onClick={() => applyTransfer(el)}
                    className="flex w-full items-baseline justify-between gap-3 rounded px-2 py-1.5 text-left hover:bg-raised"
                  >
                    <span className="min-w-0">
                      <span className="text-[13px] text-ink">{el.web_name}</span>
                      <span className="ml-2 text-[11px] text-faint">
                        {teams.get(el.team)?.short_name}
                        {el.status !== "a" ? ` · ${el.status}` : ""}
                      </span>
                    </span>
                    <span className="tnum shrink-0 text-[12px]">
                      <span className="text-muted">{price(el.now_cost)}</span>
                      <span className="ml-2 font-semibold text-model">{dec(mu < 0 ? null : mu, 1)}</span>
                      <span className="ml-2 text-faint">
                        {pStart == null ? "" : `${Math.round(pStart * 100)}%`}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={confirm != null} onOpenChange={(open) => !open && setConfirm(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-void/70" />
          <Dialog.Content className="fixed inset-x-4 top-[28vh] z-50 mx-auto max-w-sm rounded-xl border border-edge bg-panel p-5 shadow-xl outline-none">
            <Dialog.Title className="text-[14px] font-medium">
              {confirm === "chip"
                ? `Play ${CHIP_LABEL[pendingChipName ?? ""] ?? pendingChipName}?`
                : confirm === "hit"
                  ? `Take a −${hit} hit?`
                  : "Confirm transfers?"}
            </Dialog.Title>
            <p className="mt-2 text-[12px] leading-relaxed text-muted">
              {confirm === "chip"
                ? "Chips are one-shot for this half. They are not played until you save lineup or confirm transfers."
                : confirm === "hit"
                  ? "Hits are deducted from this gameweek’s points and cannot be undone."
                  : "These transfers will be submitted to FPL."}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Dialog.Close className="rounded-md px-3 py-1.5 text-[12px] text-muted">
                Cancel
              </Dialog.Close>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  if (confirm === "chip") confirmChip();
                  else void saveTransfers(transferChip);
                  setConfirm(null);
                }}
                className="rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model"
              >
                Confirm
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
