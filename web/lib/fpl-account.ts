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
  chance_of_playing_next_round?: number | null;
  selected_by_percent: string;
  form?: string;
  points_per_game?: string;
  total_points?: number;
  event_points?: number;
  bonus?: number;
  ict_index?: string;
  influence?: string;
  creativity?: string;
  threat?: string;
  transfers_in_event?: number;
  transfers_out_event?: number;
  cost_change_event?: number;
  cost_change_start?: number;
};

/** Raw fixture row from fantasy.premierleague.com/api/fixtures/ */
export type FplApiFixture = {
  event: number | null;
  team_h: number;
  team_a: number;
  team_h_difficulty: number;
  team_a_difficulty: number;
  finished: boolean;
};

export type UpcomingFixture = {
  gw: number;
  opponentCode: string;
  home: boolean;
  fdr: number | null;
};

export type BootstrapEvent = {
  id: number;
  name: string;
  deadline_time: string | null;
  is_current: boolean;
  is_next: boolean;
  finished: boolean;
  average_entry_score?: number | null;
  highest_score?: number | null;
};

export type BootstrapTeam = {
  id: number;
  name: string;
  short_name: string;
};

export type BootstrapStatic = {
  elements: BootstrapElement[];
  teams: BootstrapTeam[];
  events?: BootstrapEvent[];
  total_players?: number;
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

/** Next `count` gameweeks from `fromGw` for a club, with FDR from that team's perspective. */
export function upcomingFixturesForTeam(
  fixtures: FplApiFixture[],
  teamId: number,
  teamCodes: Map<number, string>,
  fromGw: number,
  count = 3,
): UpcomingFixture[] {
  const out: UpcomingFixture[] = [];
  for (let gw = fromGw; gw < fromGw + count; gw++) {
    const f = fixtures.find(
      (row) =>
        row.event === gw && (row.team_h === teamId || row.team_a === teamId),
    );
    if (!f) {
      out.push({ gw, opponentCode: "—", home: true, fdr: null });
      continue;
    }
    const home = f.team_h === teamId;
    const oppId = home ? f.team_a : f.team_h;
    out.push({
      gw,
      opponentCode: teamCodes.get(oppId) ?? String(oppId),
      home,
      fdr: home ? f.team_h_difficulty : f.team_a_difficulty,
    });
  }
  return out;
}
