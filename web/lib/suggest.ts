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

export type SuggestPlan = {
  k: number;
  hit: number;
  next_xi_mu: number;
  score: number;
  delta_mu: number;
  bank: number;
  captain: string;
  vice: string;
  captain_id: number;
  vice_id: number;
  xi_ids: number[];
  moves: SuggestMove[];
};

export type SuggestResult = {
  source: string;
  strategy: string;
  next_gw: number;
  roll_mu: number;
  plans: SuggestPlan[];
};
