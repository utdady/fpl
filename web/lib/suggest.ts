/** Shared JSON shape from `fpl.py suggest --json`. Safe for client imports. */

export type SuggestMove = {
  out_id: number;
  out_name: string;
  in_id: number;
  in_name: string;
  pos: string;
  selling_price: number;
  purchase_price: number;
};

/** XI starter with low modeled P(start) — can suppress captaincy for premiums. */
export type SuggestMinutesFlag = {
  id: number;
  name: string;
  pos: string;
  p_start: number;
  mu: number;
  utility: number;
};

export type SuggestPlan = {
  k: number;
  hit: number;
  next_xi_mu: number;
  next_xi_utility: number;
  score: number;
  delta: number;
  /** Compat alias of delta (utility − hit vs roll). */
  delta_mu?: number;
  bank: number;
  captain: string;
  vice: string;
  captain_id: number;
  vice_id: number;
  /** Captain chosen by highest next_mu (xP) in the XI. */
  captain_mu?: number;
  captain_utility?: number;
  captain_p_start?: number;
  captain_pos?: string;
  xi_ids: number[];
  incoming_ids: number[];
  outgoing_ids: number[];
  minutes_flags?: SuggestMinutesFlag[];
  moves: SuggestMove[];
};

export type SuggestResult = {
  source: string;
  strategy: string;
  next_gw: number;
  mode: "NORMAL_TRANSFER" | "WILDCARD" | "FREE_HIT" | string;
  objective: string;
  squad_objective: string | null;
  displayed_payoff: string;
  diversify_n: number;
  roll_utility: number;
  roll_mu: number;
  plans: SuggestPlan[];
};
