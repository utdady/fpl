"use client";

import { useMemo, useState } from "react";

import { ModelProvenance } from "./model-provenance";
import { BoomQuadrant, QuadrantLegend } from "./charts/boom-quadrant";
import { LooChart } from "./charts/loo-chart";
import { MuWaterfall } from "./charts/mu-waterfall";
import { OutcomeDistribution } from "./charts/outcome-distribution";
import { Pitch } from "./pitch";
import { Section } from "./ui/section";
import { Stat, StatRow } from "./ui/stat";
import { dec, formation, price, seasonLabel } from "@/lib/format";
import { playerDiagAt } from "@/lib/player-diagnostics";
import type { CellPlayer } from "./player-cell";
import type {
  Audit,
  GwDiagnostics,
  Manifest,
  PlayerSeries,
  Predictions,
  StrategyKey,
} from "@/lib/types";

const STRATEGIES: StrategyKey[] = ["safe", "balanced", "aggressive"];

function diagPlayerToCell(
  p: GwDiagnostics["squads"]["balanced"]["players"][0],
): CellPlayer {
  return {
    id: p.id,
    name: p.name,
    pos: p.pos,
    cost: p.cost,
    teamCode: p.teamCode,
    mu: p.mu,
    sigma: null,
    pStart: null,
    p10: null,
    pts: null,
    mins: null,
    captain: p.captain,
    vice: p.vice,
  };
}

export function AuditBoard({
  season,
  gw,
  audit,
  diagnostics,
  predictions,
  manifest,
}: {
  season: string;
  gw: number;
  audit: Audit | null;
  diagnostics: GwDiagnostics | null;
  predictions: Predictions | null;
  manifest?: Manifest;
}) {
  const [strategy, setStrategy] = useState<StrategyKey>("balanced");
  const [focusId, setFocusId] = useState<number | null>(null);

  const squad = diagnostics?.squads[strategy] ?? null;
  const xi = squad?.players.filter((p) => p.xi).map(diagPlayerToCell) ?? [];
  const bench = squad?.players.filter((p) => !p.xi).map(diagPlayerToCell) ?? [];

  const quadrantPoints = useMemo(() => {
    if (!predictions) return [];
    return Object.entries(predictions.players)
      .map(([id, series]) => {
        const slice = playerDiagAt(series, gw);
        if (slice?.p0 == null) return null;
        const i = series.gw.indexOf(gw);
        return {
          id: Number(id),
          name: series.name,
          pos: series.pos,
          p0: slice.p0,
          p10: series.p10[i] ?? 0,
          mu: series.mu[i] ?? 0,
          highlight: focusId === Number(id),
        };
      })
      .filter((p): p is NonNullable<typeof p> => p != null);
  }, [predictions, gw, focusId]);

  const focusSeries: PlayerSeries | null =
    focusId != null && predictions
      ? (predictions.players[String(focusId)] ?? null)
      : null;
  const focusDiag = focusSeries ? playerDiagAt(focusSeries, gw) : null;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Audit</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          Why each player is in the fifteen, priced in objective points. LOO and
          strategy squads are live re-solves; sim quantiles on the quadrant use the
          frozen GW record.
        </p>
        <div className="mt-3 grid max-w-2xl gap-2 sm:grid-cols-2">
          {(audit || diagnostics) && (
            <ModelProvenance
              role="live_resolv"
              config={audit?.model_config ?? diagnostics?.model_config ?? manifest?.production}
              manifest={manifest}
              compact
            />
          )}
          {predictions?.model_config && (
            <ModelProvenance
              role="frozen_record"
              config={predictions.model_config}
              manifest={manifest}
              compact
            />
          )}
        </div>
      </div>

      {!audit && !diagnostics && (
        <Section title="No audit export for this season" source={`season/${season}/audit.json`}>
          <p className="text-[12px] text-muted">
            Run{" "}
            <span className="font-mono text-faint">python -m engine.capture --gw N --diagnostics</span>{" "}
            then <span className="font-mono text-faint">python scripts/export_ui.py</span>.
          </p>
        </Section>
      )}

      {audit && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Section
            title="Leave-one-out delta"
            subtitle={audit.baseline_u_note}
            source="records/audit_loo.csv"
            caveats={audit.caveats}
          >
            <LooChart rows={audit.loo} />
            {audit.as_of && (
              <p className="mt-3 text-[10px] text-faint">Snapshot {audit.as_of}</p>
            )}
          </Section>

          <Section title="Lock / exclude counterfactuals" source="records/audit_counterfactual.csv">
            {audit.counterfactuals.length === 0 ? (
              <p className="text-[12px] text-muted">No counterfactual rows exported.</p>
            ) : (
              <ul className="space-y-2 text-[12px]">
                {audit.counterfactuals.map((cf) => (
                  <li key={`${cf.id}-${cf.action}`} className="rounded-md border border-edge px-3 py-2">
                    <span className="font-medium text-ink">{cf.name}</span>
                    <span className="text-muted"> · {cf.action}</span>
                    <div className="tnum mt-1 text-muted">
                      Δ objective {dec(cf.delta, 2)} · baseline U {dec(cf.baseline_u, 1)} →{" "}
                      {dec(cf.alt_u, 1)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      )}

      {diagnostics && squad && (
        <Section
          title={`Per-strategy fifteen — ${seasonLabel(season)} GW${gw}`}
          subtitle={`Formation ${formation(xi.map((p) => p.pos))}. C ${squad.captain}, VC ${squad.vice}.`}
          source={`records/gw${String(gw).padStart(2, "0")}_diagnostics.json`}
          caveats={diagnostics.caveats}
          actions={
            <div className="flex gap-1">
              {STRATEGIES.map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStrategy(key)}
                  className={`rounded-md px-2.5 py-1 font-mono text-[11px] ${
                    key === strategy
                      ? "bg-model/15 text-model"
                      : "text-muted hover:bg-raised/60"
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
            <Stat label="XI size" value={xi.length} />
          </StatRow>
          <div className="mt-5">
            <Pitch players={xi} bench={bench} season={season} gw={gw} />
          </div>
        </Section>
      )}

      {predictions?.has_diagnostics && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Section
            title="Boom-or-bust quadrant"
            subtitle="Sim P(0) vs P(10+) for the frozen pool. Click a LOO name below to highlight."
            source="predictions.json diagnostics columns"
          >
            <BoomQuadrant points={quadrantPoints} onSelect={setFocusId} />
            <QuadrantLegend />
            {audit && (
              <div className="mt-3 flex flex-wrap gap-1">
                {audit.loo.slice(0, 8).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setFocusId(r.id)}
                    className={`rounded px-2 py-0.5 text-[10px] ${
                      focusId === r.id ? "bg-model/15 text-model" : "text-muted hover:bg-raised/60"
                    }`}
                  >
                    {r.name}
                  </button>
                ))}
              </div>
            )}
          </Section>

          <Section
            title={focusSeries ? focusSeries.name : "Player diagnostics"}
            subtitle={
              focusSeries
                ? "Contribution waterfall and sim quantiles for the selected GW."
                : "Select a player from the quadrant or LOO list."
            }
          >
            {focusSeries && focusDiag?.quantiles ? (
              <div className="space-y-4">
                <OutcomeDistribution
                  quantiles={focusDiag.quantiles}
                  actual={focusDiag.actual}
                  mu={focusDiag.mu}
                />
                {focusDiag.components && (
                  <div>
                    <div className="label-xs mb-2">μ components (sim means)</div>
                    <MuWaterfall components={focusDiag.components} />
                  </div>
                )}
                {focusDiag.p0 != null && (
                  <p className="tnum text-[11px] text-muted">
                    P(0) = {dec(focusDiag.p0 * 100, 1)}% · not the same as 1 − p_start
                  </p>
                )}
              </div>
            ) : (
              <p className="text-[12px] text-muted">Pick a player to inspect outcome shape.</p>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}
