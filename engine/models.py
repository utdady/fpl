"""Core dataclasses for a timestamped FPL snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


POS_BY_ID = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass(frozen=True)
class ScoringRules:
    long_play: int
    short_play: int
    goals_scored: dict[str, int]
    assists: int
    clean_sheets: dict[str, int]
    defensive_contribution: dict[str, int]
    goals_conceded: dict[str, int]
    saves: int
    yellow_cards: int
    red_cards: int
    bonus: int
    dc_threshold: dict[str, int]


@dataclass(frozen=True)
class SquadRules:
    squad_size: int
    squad_play: int
    budget: int
    team_limit: int
    squad_select: dict[str, int]
    min_play: dict[str, int]
    max_play: dict[str, int]


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    short_name: str
    strength_home: int
    strength_away: int


@dataclass(frozen=True)
class Event:
    id: int
    name: str
    deadline: str | None
    is_current: bool
    is_next: bool
    finished: bool


@dataclass(frozen=True)
class Fixture:
    id: int
    event: int | None
    team_h: int
    team_a: int
    kickoff: str | None
    finished: bool
    fdr_home: int | None
    fdr_away: int | None


@dataclass(frozen=True)
class Player:
    id: int
    web_name: str
    first_name: str
    second_name: str
    element_type: int
    position: str
    team_id: int
    now_cost: int
    status: str
    can_select: bool
    news: str
    chance_this: int | None
    chance_next: int | None
    minutes: int
    starts: int
    xg90: float
    xa90: float
    xgc90: float
    dc90: float
    saves90: float
    yellow: int
    red: int
    bonus: int
    goals: int
    assists_n: int
    total_points: int
    games_hint: int
    pen_order: int | None
    corners_order: int | None
    selected_by: float
    ep_next: float | None


@dataclass
class Snapshot:
    as_of: datetime
    season_label: str
    scoring: ScoringRules
    squad: SquadRules
    teams: dict[int, Team]
    events: list[Event]
    fixtures: list[Fixture]
    players: list[Player]

    def next_event(self) -> Event:
        for e in self.events:
            if e.is_next:
                return e
        for e in self.events:
            if not e.finished:
                return e
        return self.events[0]

    def fixtures_for(self, event_id: int) -> list[Fixture]:
        return [f for f in self.fixtures if f.event == event_id and not f.finished]

    def team(self, team_id: int) -> Team:
        return self.teams[team_id]


@dataclass
class GWProjection:
    player_id: int
    event_id: int
    n_fixtures: int
    mu: float
    sigma: float
    p_start: float
    p_sub: float
    p_60: float
    p_10_plus: float
    p90: float


@dataclass
class PlayerProjection:
    player: Player
    by_gw: dict[int, GWProjection]
    horizon_mu: float
    horizon_sigma: float
    horizon_utility: float
    next_mu: float
    next_sigma: float
    next_p_start: float
    next_p_60: float
    next_p_10: float
    next_utility: float


@dataclass
class SquadSolution:
    players: list[Player]
    xi: list[Player]
    bench: list[Player]
    captain: Player
    vice: Player
    cost: int
    bank: int
    horizon_utility: float
    next_xi_mu: float
    next_xi_utility: float
    alternatives: list[tuple[str, Player, float]]
    strategy: str
    horizon_gws: list[int]
