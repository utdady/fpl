"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import { EntryPitch } from "./entry-pitch";
import { Section } from "./ui/section";
import { fetchEntryBundle, type FplEntry } from "@/lib/fpl-entry";
import {
  addEntry,
  loadTracked,
  removeEntry,
  saveTracked,
  setCompareId,
  setMine,
  type TrackedState,
} from "@/lib/tracked-teams";
import type { ComparePoolPlayer } from "@/lib/team-compare";
import type { StrategyKey } from "@/lib/types";

export type PoolPlayer = ComparePoolPlayer;

export function TeamTracker({
  gw,
  season,
  pool,
  balancedIds: _balancedIds,
}: {
  gw: number;
  season: string;
  pool: PoolPlayer[];
  balancedIds: number[];
  strategy: StrategyKey;
}) {
  // null until localStorage is read — never persist the empty initial state
  // (that race wiped saved entry IDs on first paint).
  const [state, setState] = useState<TrackedState | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [names, setNames] = useState<Record<number, string>>({});

  useEffect(() => {
    setState(loadTracked());
  }, []);

  useEffect(() => {
    if (state == null) return;
    saveTracked(state);
  }, [state]);

  function add() {
    const id = Number(draft.trim());
    if (!Number.isInteger(id) || id <= 0) {
      setError("Entry ID is the number in your FPL URL, e.g. /entry/123456/");
      return;
    }
    setError(null);
    setDraft("");
    setState((prev) => (prev ? addEntry(prev, id) : prev));
  }

  function patch(next: TrackedState) {
    setState(next);
  }

  if (state == null) {
    return <p className="text-[12px] text-muted">Loading saved entries…</p>;
  }

  return (
    <div className="space-y-5">
      <Section
        title="Saved entries"
        subtitle="IDs stay in this browser. Mark Mine for compare baseline. The FPL API is public; you do not log in."
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

        {state.mine.length > 1 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
            <span className="text-muted">Compare baseline</span>
            <select
              value={state.compareId ?? ""}
              onChange={(e) =>
                patch(setCompareId(state, e.target.value ? Number(e.target.value) : null))
              }
              className="rounded-md border border-edge bg-raised px-2 py-1 text-[12px] outline-none focus:border-edge-bright"
            >
              {state.mine.map((id) => (
                <option key={id} value={id}>
                  {names[id] ?? `Entry ${id}`}
                </option>
              ))}
            </select>
          </div>
        )}
      </Section>

      {state.entries.length === 0 && (
        <p className="text-[12px] text-muted">No teams yet. Paste an entry ID from your FPL URL.</p>
      )}

      <ul className="space-y-2">
        {state.entries.map((id) => (
          <TrackedRow
            key={id}
            id={id}
            gw={gw}
            season={season}
            pool={pool}
            isMine={state.mine.includes(id)}
            onMine={(mine) => patch(setMine(state, id, mine))}
            onRemove={() => patch(removeEntry(state, id))}
            onName={(name) => setNames((prev) => (prev[id] === name ? prev : { ...prev, [id]: name }))}
          />
        ))}
      </ul>
    </div>
  );
}

function TrackedRow({
  id,
  gw,
  season,
  pool,
  isMine,
  onMine,
  onRemove,
  onName,
}: {
  id: number;
  gw: number;
  season: string;
  pool: PoolPlayer[];
  isMine: boolean;
  onMine: (mine: boolean) => void;
  onRemove: () => void;
  onName: (name: string) => void;
}) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [entry, setEntry] = useState<FplEntry | null>(null);
  const [picks, setPicks] = useState<Awaited<ReturnType<typeof fetchEntryBundle>>["picks"]>([]);
  const [picksOpen, setPicksOpen] = useState(false);
  const [preview, setPreview] = useState(false);

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
        onName(bundle.entry.name);
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
    // onName is a setState wrapper from parent; omit to avoid re-fetch loops
  }, [id, gw]);

  const subtitle = useMemo(() => {
    if (status === "loading") return "Loading…";
    if (status === "error" || !entry) return "Could not load entry";
    return `${entry.summary_overall_points ?? "—"} pts · rank ${entry.summary_overall_rank ?? "—"}`;
  }, [entry, status]);

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-md border border-edge bg-raised/30 px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-ink">
          {entry?.name ?? `Entry ${id}`}
        </div>
        <div className="tnum text-[11px] text-muted">{subtitle}</div>
      </div>

      <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted">
        <input
          type="checkbox"
          checked={isMine}
          onChange={(e) => onMine(e.target.checked)}
          className="accent-[var(--color-model)]"
        />
        Mine
      </label>

      <Dialog.Root open={preview} onOpenChange={setPreview}>
        <Dialog.Trigger asChild>
          <button
            type="button"
            disabled={!picksOpen || picks.length === 0}
            className="rounded-md border border-edge px-2.5 py-1 text-[11px] text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            Preview
          </button>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-void/70" />
          <Dialog.Content className="fixed inset-x-4 top-[8vh] z-50 mx-auto max-h-[84vh] max-w-2xl overflow-y-auto rounded-xl border border-edge bg-panel p-4 shadow-xl outline-none">
            <div className="mb-3 flex items-start justify-between gap-3">
              <Dialog.Title className="text-[14px] font-medium text-ink">
                {entry?.name ?? `Entry ${id}`}
              </Dialog.Title>
              <Dialog.Close className="text-[11px] text-muted hover:text-ink">Close</Dialog.Close>
            </div>
            <EntryPitch picks={picks} pool={pool} season={season} gw={gw} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Link
        href={`/teams/${id}`}
        className="rounded-md bg-model/15 px-2.5 py-1 text-[11px] text-model"
      >
        Open
      </Link>

      <button type="button" onClick={onRemove} className="text-[11px] text-muted hover:text-risk">
        Remove
      </button>
    </li>
  );
}
