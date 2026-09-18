"use client";

import { useState } from "react";

import { Section } from "./ui/section";
import { Stat, StatRow } from "./ui/stat";
import { accountJson } from "@/lib/fpl-account";
import { price, signed } from "@/lib/format";
import type { SuggestPlan, SuggestResult } from "@/lib/suggest";

function planDelta(plan: SuggestPlan): number {
  return plan.delta ?? plan.delta_mu ?? 0;
}

function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

function captainWarn(plan: SuggestPlan): string | null {
  if (plan.captain_pos === "GKP") return "GK captain — unusual; check minutes on outfield premiums";
  if (plan.captain_p_start != null && plan.captain_p_start < 0.5) {
    return "Captain P(start) under 50%";
  }
  return null;
}

function CaptainLine({ plan }: { plan: SuggestPlan }) {
  const warn = captainWarn(plan);
  return (
    <div className="mt-1 space-y-0.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[11px]">
        <span>
          <span className="text-faint">C</span>{" "}
          <span className={warn ? "text-risk" : "text-ink"}>{plan.captain}</span>
        </span>
        {plan.captain_mu != null ? (
          <span className="tnum text-muted">xP {plan.captain_mu.toFixed(1)}</span>
        ) : null}
        {plan.captain_p_start != null ? (
          <span className="tnum text-muted">start {pct(plan.captain_p_start)}</span>
        ) : null}
        {plan.vice ? (
          <span>
            <span className="text-faint">VC</span> {plan.vice}
          </span>
        ) : null}
      </div>
      {warn ? <p className="text-[11px] text-risk">{warn}</p> : null}
    </div>
  );
}

/** Compact table — avoids a red run-on sentence when half the XI is flagged. */
function MinutesPanel({ plan, title }: { plan: SuggestPlan; title: string }) {
  const flags = [...(plan.minutes_flags ?? [])].sort(
    (a, b) => a.p_start - b.p_start || b.mu - a.mu,
  );
  if (flags.length === 0) return null;

  const majority = flags.length >= 6;
  return (
    <div className="mt-3 border-t border-edge/50 pt-3">
      <p className="text-[11px] text-muted">
        <span className="font-medium text-ink">{title}</span>
        {" · "}
        {majority
          ? `${flags.length}/11 below 50% start chance — minutes model is suppressing most of the XI`
          : `${flags.length} starter${flags.length === 1 ? "" : "s"} below 50% start chance`}
      </p>
      <table className="mt-2 w-full max-w-md text-left text-[11px]">
        <thead>
          <tr className="text-faint">
            <th className="py-0.5 pr-3 font-medium">Player</th>
            <th className="py-0.5 pr-2 font-medium">Pos</th>
            <th className="py-0.5 pr-2 font-medium">Start</th>
            <th className="py-0.5 font-medium">xP</th>
          </tr>
        </thead>
        <tbody>
          {flags.map((f) => (
            <tr key={f.id} className="border-t border-edge/30">
              <td className="py-0.5 pr-3 text-ink">{f.name}</td>
              <td className="py-0.5 pr-2 text-muted">{f.pos}</td>
              <td className="tnum py-0.5 pr-2 text-risk">{pct(f.p_start)}</td>
              <td className="tnum py-0.5 text-muted">{f.mu.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CurrentVsBestCard({
  result,
  pendingCount,
  onStage,
}: {
  result: SuggestResult;
  pendingCount: number;
  onStage: (plan: SuggestPlan) => void;
}) {
  const roll = result.plans.find((p) => p.k === 0);
  const best = result.plans[0];
  if (!roll || !best) return null;

  const isRollBest = best.k === 0;
  const gain = best.score - roll.score;

  return (
    <div className="rounded-xl border border-edge bg-raised/40 px-4 py-3">
      <div className="label-xs text-faint">
        Next GW {result.next_gw} · utility score (not FPL points) · captain = highest xP in XI
      </div>

      <StatRow>
        <Stat
          label="Current XI + C"
          value={roll.score.toFixed(1)}
          tone="neutral"
          note={<CaptainLine plan={roll} />}
        />
        {!isRollBest ? (
          <>
            <Stat
              label={`Best plan · ${best.k} transfer${best.k === 1 ? "" : "s"}${
                best.hit > 0 ? ` · −${best.hit} hit` : ""
              }`}
              value={best.score.toFixed(1)}
              tone="model"
              note={<CaptainLine plan={best} />}
            />
            <Stat
              label="Improvement"
              value={signed(gain, 1)}
              tone={gain >= 0 ? "actual" : "risk"}
              note={best.bank != null ? `Bank ${price(best.bank)}` : undefined}
            />
          </>
        ) : (
          <Stat
            label="Best plan"
            value="Hold"
            tone="actual"
            note="No transfer beats holding this week"
          />
        )}
      </StatRow>

      <MinutesPanel plan={roll} title={isRollBest ? "XI minutes" : "Current XI minutes"} />
      {!isRollBest ? <MinutesPanel plan={best} title="Best-plan XI minutes" /> : null}

      {!isRollBest && best.moves.length > 0 ? (
        <ul className="mt-3 space-y-1 border-t border-edge/50 pt-3 text-[12px]">
          {best.moves.map((m) => (
            <li key={`${m.out_id}-${m.in_id}`} className="flex justify-between gap-3">
              <span>
                {m.out_name}
                <span className="text-faint"> → </span>
                {m.in_name}
              </span>
              <span className="tnum text-muted">{m.pos}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-edge/50 pt-3">
        <p className="text-[11px] text-faint">
          Score = modeled XI + captain utility after hit — not a guaranteed FPL score.
        </p>
        {!isRollBest && best.moves.length > 0 ? (
          <button
            type="button"
            onClick={() => onStage(best)}
            className="shrink-0 rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model"
          >
            {pendingCount > 0 ? "Replace pending" : "Stage plan"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function SuggestPlans({
  pendingCount,
  onStage,
}: {
  pendingCount: number;
  onStage: (plan: SuggestPlan) => void;
}) {
  const [result, setResult] = useState<SuggestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Conservative default: free transfers only. Hits are an explicit aggressive option. */
  const [allowHit, setAllowHit] = useState(false);

  async function rank() {
    setBusy(true);
    setError(null);
    const q = allowHit ? "?allow_hit=1" : "?allow_hit=0";
    const res = await accountJson<SuggestResult>(`/api/account/suggest${q}`);
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setResult(res.data);
  }

  const modeLabel =
    result?.mode === "WILDCARD"
      ? "Wildcard — squad objective is horizon utility; table shows next-GW payoff"
      : result?.mode === "FREE_HIT"
        ? "Free Hit — squad objective is horizon utility; table shows next-GW payoff"
        : result
          ? "Next-GW FT-spending optimizer (not a selective “should you transfer?” advisor)"
          : null;

  return (
    <Section
      title="Next-GW transfer plans"
      subtitle="Finds the highest projected next-GW XI+C plan given your available free transfers. Not advice to hit confirm."
      source={result?.source}
      caveats={[
        "Spends available FTs toward next-GW next_utility — it does not decide whether banking is wiser.",
        "Default is free transfers only. Allow hit is an aggressive opt-in (−4 for FT+1).",
        "Candidates are diversified (exclude prior ins), not guaranteed global top-N.",
        "First run may take a minute while projections cache.",
      ]}
      actions={
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-[11px] text-muted">
            <input
              type="checkbox"
              checked={allowHit}
              disabled={busy}
              onChange={(e) => {
                setAllowHit(e.target.checked);
                setResult(null);
              }}
              className="accent-model"
            />
            Allow hit (−4)
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() => void rank()}
            className="shrink-0 rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model disabled:opacity-40"
          >
            {busy ? "Ranking…" : result ? "Re-rank" : "Rank plans"}
          </button>
        </div>
      }
    >
      {error && <p className="text-[12px] text-risk">{error}</p>}
      {!result && !error && !busy && (
        <p className="text-[12px] text-muted">
          Ranks legal plans using 0–FT transfers
          {allowHit ? " (plus one optional hit)" : ""}. Staging does not submit to FPL.
        </p>
      )}
      {result && (
        <div className="space-y-3">
          <p className="text-[11px] text-muted">
            <span className="font-medium text-ink">{result.mode}</span>
            {modeLabel ? ` · ${modeLabel}` : null}
            {result.squad_objective ? ` · squad: ${result.squad_objective}` : null}
            {allowHit ? " · hit mode on" : " · free transfers only"}
          </p>

          <CurrentVsBestCard result={result} pendingCount={pendingCount} onStage={onStage} />

          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-[12px]">
              <thead>
                <tr className="border-b border-edge text-[11px] text-faint">
                  <th className="py-1.5 pr-3 font-medium">k</th>
                  <th className="py-1.5 pr-3 font-medium">hit</th>
                  <th className="py-1.5 pr-3 font-medium">Δ</th>
                  <th className="py-1.5 pr-3 font-medium">score</th>
                  <th className="py-1.5 pr-3 font-medium">XI+C μ</th>
                  <th className="py-1.5 pr-3 font-medium">moves</th>
                  <th className="py-1.5 pr-3 font-medium">C</th>
                  <th className="py-1.5 font-medium" />
                </tr>
              </thead>
              <tbody>
                {result.plans.map((plan, i) => {
                  const d = planDelta(plan);
                  return (
                    <tr key={`${plan.k}-${plan.hit}-${i}`} className="border-b border-edge/40">
                      <td className="tnum py-1.5 pr-3">{plan.k}</td>
                      <td className={`tnum py-1.5 pr-3 ${plan.hit ? "text-risk" : "text-muted"}`}>
                        {plan.hit ? `−${plan.hit}` : "0"}
                      </td>
                      <td className={`tnum py-1.5 pr-3 ${d >= 0 ? "text-actual" : "text-risk"}`}>
                        {signed(d, 2)}
                      </td>
                      <td className="tnum py-1.5 pr-3 text-model">{plan.score.toFixed(1)}</td>
                      <td className="tnum py-1.5 pr-3 text-muted">{plan.next_xi_mu.toFixed(1)}</td>
                      <td className="py-1.5 pr-3">
                        {plan.moves.length === 0
                          ? "roll"
                          : plan.moves.map((m) => `${m.out_name} → ${m.in_name}`).join(", ")}
                      </td>
                      <td className="py-1.5 pr-3">
                        <div className={captainWarn(plan) ? "text-risk" : "text-ink"}>
                          {plan.captain}
                        </div>
                        {plan.captain_mu != null || plan.captain_p_start != null ? (
                          <div className="tnum text-[10px] text-faint">
                            {plan.captain_mu != null ? `xP ${plan.captain_mu.toFixed(1)}` : null}
                            {plan.captain_mu != null && plan.captain_p_start != null
                              ? " · "
                              : null}
                            {plan.captain_p_start != null
                              ? `start ${pct(plan.captain_p_start)}`
                              : null}
                          </div>
                        ) : null}
                      </td>
                      <td className="py-1.5 text-right">
                        {plan.moves.length > 0 ? (
                          <button
                            type="button"
                            onClick={() => onStage(plan)}
                            className="rounded-md border border-edge px-2 py-1 text-[11px] hover:border-edge-bright"
                          >
                            {pendingCount > 0 ? "Replace pending" : "Stage"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Section>
  );
}
