"use client";

import { useState } from "react";

import { ModelProvenance } from "./model-provenance";
import { Pitch } from "./pitch";
import { Section } from "./ui/section";
import { Stat, StatRow } from "./ui/stat";
import { SNAPSHOT_DAY } from "@/lib/snapshot";
import { formation, price } from "@/lib/format";
import type { CellPlayer } from "./player-cell";
import type { Strategies, StrategyKey, StrategyPlayer } from "@/lib/types";

const ORDER: StrategyKey[] = ["safe", "balanced", "aggressive"];

function toCell(p: StrategyPlayer): CellPlayer {
  return {
    id: p.id,
    name: p.name,
    pos: p.pos,
    cost: p.cost,
    teamCode: p.teamCode,
    mu: p.mu,
    sigma: p.sigma,
    pStart: p.p_start,
    p10: p.p10,
    pts: null,
    mins: null,
    captain: p.captain,
    vice: p.vice,
  };
}

export function StrategyBoard({
  season,
  data,
}: {
  season: string;
  data: Strategies;
}) {
  const [strategy, setStrategy] = useState<StrategyKey>("balanced");
  const squad = data.squads[strategy];
  const xi = squad.players.filter((p) => p.xi).map(toCell);
  const bench = squad.players.filter((p) => p.bench).map(toCell);

  return (
    <div className="space-y-5">
      <ModelProvenance
        role="live_resolv"
        config={data.model_config}
        compact
      />
      <Section
        title={`${strategy} fifteen — ${season.replace("-", "/")} GW${data.gw}`}
        subtitle={`Formation ${formation(xi.map((p) => p.pos))}. Captain ${squad.captain}, vice ${squad.vice}. Strategy changes the projected utility, not the constraint set.`}
        source="scripts/export_strategies.py from engine.optimize.solve_squad"
        caveats={data.caveats}
        actions={
          <div className="flex gap-1">
            {ORDER.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setStrategy(key)}
                className={`rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors ${
                  key === strategy
                    ? "bg-model/15 text-model"
                    : "text-muted hover:bg-raised/60 hover:text-ink"
                }`}
              >
                {key}
              </button>
            ))}
          </div>
        }
      >
        <StatRow>
          <Stat label="Squad" value={price(squad.cost)} tone="model" note={`bank ${price(squad.bank)}`} />
          <Stat label="XI + C xP" value={squad.next_xi_mu.toFixed(1)} tone="model" note="next GW mu" />
          <Stat
            label="Horizon U"
            value={squad.horizon_utility.toFixed(1)}
            note={`H=${data.horizon}${SNAPSHOT_DAY ? ` · ${SNAPSHOT_DAY} snapshot` : ""}`}
          />
        </StatRow>
        <div className="mt-5">
          <Pitch players={xi} bench={bench} season={season} gw={data.gw} />
        </div>
      </Section>
    </div>
  );
}
