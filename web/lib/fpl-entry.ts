/** Shared FPL entry types + fetch via the local proxy. */

export type FplLeague = {
  id: number;
  name: string;
  short_name?: string | null;
  league_type?: string;
  scoring?: string;
  rank?: number | null;
  entry_rank?: number | null;
  entry_last_rank?: number | null;
  start_event?: number;
  entry_can_admin?: boolean;
  entry_can_leave?: boolean;
  code_privacy?: string;
  has_cup?: boolean;
};

export type FplEntry = {
  id: number;
  name: string;
  player_first_name?: string;
  player_last_name?: string;
  summary_overall_points?: number;
  summary_overall_rank?: number;
  last_deadline_bank?: number;
  current_event?: number;
  leagues?: {
    classic?: FplLeague[];
    h2h?: FplLeague[];
  };
};

export type FplPick = {
  element: number;
  position: number;
  is_captain: boolean;
  is_vice_captain: boolean;
};

export type FplHistoryRow = {
  event: number;
  points: number;
  total_points: number;
  rank: number | null;
  event_transfers: number;
  event_transfers_cost: number;
  bank: number;
  value: number;
};

export type FplTransfer = {
  element_in: number;
  element_out: number;
  event: number;
  time: string;
};

export async function fplFetch<T>(
  path: string,
): Promise<{ ok: true; data: T } | { ok: false; status: number }> {
  const response = await fetch(`/api/fpl/${path}`);
  if (!response.ok) return { ok: false, status: response.status };
  return { ok: true, data: (await response.json()) as T };
}

export async function fetchEntryBundle(
  id: number,
  fallbackGw: number,
): Promise<{
  entry: FplEntry;
  picks: FplPick[];
  picksOpen: boolean;
  history: FplHistoryRow[];
  eventId: number;
}> {
  const entryRes = await fplFetch<FplEntry>(`entry/${id}`);
  if (!entryRes.ok) throw new Error(`entry ${id}: ${entryRes.status}`);
  const entry = entryRes.data;
  const eventId = entry.current_event ?? fallbackGw;
  const [picksRes, historyRes] = await Promise.all([
    fplFetch<{ picks?: FplPick[] }>(`entry/${id}/event/${eventId}/picks`),
    fplFetch<{ current?: FplHistoryRow[] }>(`entry/${id}/history`),
  ]);
  return {
    entry,
    picks: picksRes.ok ? (picksRes.data.picks ?? []) : [],
    picksOpen: picksRes.ok,
    history: historyRes.ok ? (historyRes.data.current ?? []) : [],
    eventId,
  };
}
