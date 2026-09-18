/** v0 preference-conditioned Model A types (LOCK/BAN/BANK/CLUB). */

export const BANK_MENU_M = [0, 0.5, 1, 1.5, 2] as const;
export const CLUB_MAX_ALLOWED = [0, 1, 2] as const;

export type PrefsPayload = {
  lock?: number[];
  ban?: number[];
  min_bank_m?: number | null;
  club_max?: Record<string, number>;
};

export type SquadViewJson = {
  ids: number[];
  names: string[];
  xi: string[];
  bench: string[];
  captain: string;
  vice: string;
  cost: number;
  bank: number;
  bank_m: number;
  u: number;
  next_xi_mu: number;
  minutes_risk: number;
  club_max: number;
};

export type PrefsResult = {
  source: string;
  copy: string;
  feasible: boolean;
  message: string | null;
  model: Record<string, string | number>;
  preferences: {
    lock: number[];
    ban: number[];
    min_bank_m: number | null;
    club_max: Record<string, number>;
  };
  s1: SquadViewJson;
  s2: SquadViewJson | null;
  delta_u: number | null;
  distance: number | null;
  enters: string[];
  exits: string[];
  bank_menu_m: number[];
  club_max_allowed: number[];
};
