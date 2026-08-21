/**
 * Browser-local tracked FPL entries. Migrates the old bare ID array.
 * Does not touch records/ or the model.
 */

const STORAGE = "fpl.tracked-entries";

export type TrackedState = {
  version: 1;
  entries: number[];
  mine: number[];
  compareId: number | null;
};

const EMPTY: TrackedState = { version: 1, entries: [], mine: [], compareId: null };

function coerceIds(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  return [
    ...new Set(
      raw
        .map((n) => (typeof n === "number" ? n : Number(n)))
        .filter((n) => Number.isInteger(n) && n > 0),
    ),
  ];
}

function normalize(state: TrackedState): TrackedState {
  const entries = coerceIds(state.entries);
  const mine = coerceIds(state.mine).filter((n) => entries.includes(n));
  let compareId = state.compareId;
  if (compareId != null) {
    compareId = Number(compareId);
    if (!Number.isInteger(compareId) || !mine.includes(compareId)) compareId = mine[0] ?? null;
  }
  if (mine.length === 0) compareId = null;
  if (compareId == null && mine.length === 1) compareId = mine[0];
  return { version: 1, entries, mine, compareId };
}

export function loadTracked(): TrackedState {
  try {
    const raw = localStorage.getItem(STORAGE);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) {
      return normalize({
        version: 1,
        entries: parsed as number[],
        mine: [],
        compareId: null,
      });
    }
    if (parsed && typeof parsed === "object" && "entries" in parsed) {
      const o = parsed as Partial<TrackedState>;
      return normalize({
        version: 1,
        entries: o.entries ?? [],
        mine: o.mine ?? [],
        compareId: o.compareId ?? null,
      });
    }
    return EMPTY;
  } catch {
    return EMPTY;
  }
}

export function saveTracked(state: TrackedState): void {
  localStorage.setItem(STORAGE, JSON.stringify(normalize(state)));
}

export function addEntry(state: TrackedState, id: number): TrackedState {
  if (!Number.isInteger(id) || id <= 0 || state.entries.includes(id)) return state;
  return normalize({ ...state, entries: [...state.entries, id] });
}

export function removeEntry(state: TrackedState, id: number): TrackedState {
  return normalize({
    ...state,
    entries: state.entries.filter((x) => x !== id),
    mine: state.mine.filter((x) => x !== id),
  });
}

export function setMine(state: TrackedState, id: number, mine: boolean): TrackedState {
  if (!state.entries.includes(id)) return state;
  const nextMine = mine
    ? state.mine.includes(id)
      ? state.mine
      : [...state.mine, id]
    : state.mine.filter((x) => x !== id);
  return normalize({ ...state, mine: nextMine });
}

export function setCompareId(state: TrackedState, id: number | null): TrackedState {
  if (id != null && !state.mine.includes(id)) return state;
  return normalize({ ...state, compareId: id });
}
