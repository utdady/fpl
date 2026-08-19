export type Position = "GKP" | "DEF" | "MID" | "FWD";

export type Manifest = {
  generated_at: string;
  engine: { sha: string | null; tag: string | null };
  snapshot_as_of: string | null;
  live_season: string;
  seasons: { season: string; gws: number; has_xi: boolean; has_lab: boolean }[];
  caveats: Record<string, string>;
};

/** Columnar per-player series. Index i of every array refers to gw[i]. */
export type PlayerSeries = {
  name: string;
  team: number;
  pos: Position;
  gw: number[];
  cost: (number | null)[];
  mu: (number | null)[];
  sigma: (number | null)[];
  p_start: (number | null)[];
  p_sub: (number | null)[];
  p_60: (number | null)[];
  p10: (number | null)[];
  nfix: (number | null)[];
  pts: (number | null)[];
  min: (number | null)[];
  start: (number | null)[];
};

export type Predictions = {
  season: string;
  gws: number[];
  caveats: string[];
  players: Record<string, PlayerSeries>;
};

export type XiPlayer = {
  id: number;
  name: string;
  pos: Position;
  cost: number;
  v1_xi: 0 | 1;
  b0_xi: 0 | 1;
  v1_cap: 0 | 1;
  b0_cap: 0 | 1;
  pts: number | null;
  mins: number | null;
  v1_mu: number | null;
  b0_mu: number | null;
  v1_u: number | null;
  v1_p_start: number | null;
  flags: {
    horizon: 0 | 1;
    minutes: 0 | 1;
    fixture: 0 | 1;
    price_value: 0 | 1;
    captain: 0 | 1;
    projection_rank: 0 | 1;
  };
};

export type Xi = {
  season: string;
  caveats: string[];
  gws: Record<string, XiPlayer[]>;
};

export type DecisionGw = {
  gw: number;
  status: "clean" | "flagged" | "excluded";
  flags: string[];
  n_fixtures: number | null;
  b0: number | null;
  v1: number | null;
  v1_gw1: number | null;
  oracle: number | null;
  squad_overlap: number | null;
  xi_overlap: number | null;
  r_squad: number | null;
  r_xi: number | null;
  r_cap: number | null;
  vs_b0: number | null;
};

export type Decisions = {
  season: string;
  oracle: string;
  caveats: string[];
  gws: DecisionGw[];
};

export type Scores = {
  season: string;
  note: string;
  gws: {
    gw: number;
    n: number | null;
    mae: number | null;
    rmse: number | null;
    bias: number | null;
    spearman: number | null;
  }[];
};

export type Leakage = {
  season: string;
  threshold: number;
  threshold_note: string;
  flagged: number;
  total: number;
  caveats: string[];
  gws: {
    gw: number;
    n: number | null;
    spearman: number | null;
    mae: number | null;
    bias: number | null;
    flag: 0 | 1;
  }[];
};

export type ModelKey = "B0_xp" | "B1_season_pts" | "B2_pp90" | "B3_v1";

export type Compare = {
  season: string;
  note: string;
  caveats: string[];
  summary: Record<string, { mae: number | null; spearman: number | null; xi: number | null }>;
  models: Record<
    string,
    {
      gw: number;
      n: number | null;
      mae: number | null;
      rmse: number | null;
      bias: number | null;
      spearman: number | null;
      xi: number | null;
      cap: number | null;
    }[]
  >;
};

export type Minutes = {
  season: string;
  caveats: string[];
  buckets: {
    split: string;
    bucket: string;
    n: number | null;
    start_pct: number | null;
    zero_min_pct: number | null;
    avg_pts: number | null;
  }[];
  fits: {
    split: string;
    min_p: number | null;
    n: number | null;
    alpha: number | null;
    beta: number | null;
    p90_fitted: number | null;
    diagnostic_only: boolean;
  }[];
};

export type Panel = {
  experiment: string;
  verdict: string;
  xi_zero_min_source: string;
  caveats: string[];
  seasons: {
    season: string;
    b0_flagged: number;
    b0_total: number;
    tail_n: number | null;
    start_pct_at_90: number | null;
    p90_fitted: number | null;
    xi_zero_min: Record<string, { zero: number; slots: number; pct: number | null }>;
    v1_gw1_minus_v1_clean: number | null;
    xi_cap: Record<string, number | null>;
  }[];
};

export type Team = {
  id: number;
  code: string;
  name: string;
  strength_home: number | null;
  strength_away: number | null;
};

export type Teams = { season: string; teams: Team[] };

export type LivePlayer = {
  code: number;
  name: string;
  full: string;
  team: number;
  pos: Position;
  cost: number;
  owned: number | null;
  status: string | null;
  news: string | null;
  chance_next: number | null;
  ep_next: number | null;
  photo: string | null;
  form: number | null;
  ppg: number | null;
};

export type LivePlayers = {
  season: string;
  as_of: string | null;
  note: string;
  players: Record<string, LivePlayer>;
};

export type Fixture = {
  id: number;
  gw: number | null;
  h: number;
  a: number;
  hd: number | null;
  ad: number | null;
  kickoff: string | null;
  finished: boolean;
};

export type Fixtures = { season: string; fixtures: Fixture[] };
