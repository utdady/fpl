/** Client types + fetch helpers for the authenticated account routes. */

export type MyTeamPick = {
  element: number;
  position: number;
  selling_price: number;
  purchase_price: number;
  multiplier: number;
  is_captain: boolean;
  is_vice_captain: boolean;
};

export type MyTeamTransfers = {
  cost: number;
  status: string;
  limit: number | null;
  made: number;
  bank: number;
  value: number;
};

export type MyTeamChip = {
  name: string;
  status_for_entry: string;
  played_by_entry?: number[];
  is_pending?: boolean;
};

export type MyTeam = {
  picks: MyTeamPick[];
  chips: MyTeamChip[];
  transfers: MyTeamTransfers;
};

export type AccountSession = {
  loggedIn: boolean;
  entryId: number | null;
  name: string | null;
  playerName: string | null;
};

export type PendingTransfer = {
  element_in: number;
  element_out: number;
  purchase_price: number;
  selling_price: number;
};

export type BootstrapElement = {
  id: number;
  web_name: string;
  element_type: number;
  team: number;
  now_cost: number;
  status: string;
  news: string;
  can_select?: boolean;
  chance_of_playing_this_round: number | null;
  selected_by_percent: string;
};

export type BootstrapTeam = {
  id: number;
  name: string;
  short_name: string;
};

export type BootstrapStatic = {
  elements: BootstrapElement[];
  teams: BootstrapTeam[];
};

export async function readAccountSession(): Promise<AccountSession> {
  const res = await fetch("/api/account/session", { cache: "no-store" });
  if (!res.ok) {
    return { loggedIn: false, entryId: null, name: null, playerName: null };
  }
  return (await res.json()) as AccountSession;
}

export async function accountJson<T>(
  path: string,
  init?: RequestInit,
): Promise<{ ok: true; data: T } | { ok: false; status: number; error: string }> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (err) {
    return {
      ok: false,
      status: 0,
      error: err instanceof Error ? err.message : "Network request failed",
    };
  }
  const text = await res.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = { error: text.slice(0, 160) };
    }
  }
  if (!res.ok) {
    const err =
      json && typeof json === "object" && "error" in json
        ? String((json as { error: unknown }).error)
        : `Request failed (${res.status})`;
    return { ok: false, status: res.status, error: err };
  }
  return { ok: true, data: json as T };
}
