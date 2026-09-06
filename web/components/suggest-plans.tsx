"use client";

import { useState } from "react";

import { Section } from "./ui/section";
import { accountJson } from "@/lib/fpl-account";
import { signed } from "@/lib/format";
import type { SuggestPlan, SuggestResult } from "@/lib/suggest";

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

  async function rank() {
    setBusy(true);
    setError(null);
    const res = await accountJson<SuggestResult>("/api/account/suggest?allow_hit=1");
    setBusy(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setResult(res.data);
  }

  return (
    <Section
      title="Suggested plans"
      subtitle="From your saved 15, using live production projections. Not advice to hit confirm."
      source={result?.source}
      caveats={[
        "Ranked by next-GW XI + captain μ minus hit. Hits are optional comparisons, not a recommendation to take them.",
        "First run may take a minute while projections cache.",
      ]}
      actions={
        <button
          type="button"
          disabled={busy}
          onClick={() => void rank()}
          className="shrink-0 rounded-md bg-model/15 px-3 py-1.5 text-[12px] text-model disabled:opacity-40"
        >
          {busy ? "Ranking…" : result ? "Re-rank" : "Rank plans"}
        </button>
      }
    >
      {error && <p className="text-[12px] text-risk">{error}</p>}
      {!result && !error && !busy && (
        <p className="text-[12px] text-muted">
          Rank 0–FT transfers (and one optional hit) against the current engine. Does not
          submit anything.
        </p>
      )}
      {result && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-[12px]">
            <thead>
              <tr className="border-b border-edge text-[11px] text-faint">
                <th className="py-1.5 pr-3 font-medium">k</th>
                <th className="py-1.5 pr-3 font-medium">hit</th>
                <th className="py-1.5 pr-3 font-medium">Δμ</th>
                <th className="py-1.5 pr-3 font-medium">XI+C</th>
                <th className="py-1.5 pr-3 font-medium">moves</th>
                <th className="py-1.5 pr-3 font-medium">C</th>
                <th className="py-1.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {result.plans.map((plan, i) => (
                <tr key={`${plan.k}-${plan.hit}-${i}`} className="border-b border-edge/40">
                  <td className="tnum py-1.5 pr-3">{plan.k}</td>
                  <td className={`tnum py-1.5 pr-3 ${plan.hit ? "text-risk" : "text-muted"}`}>
                    {plan.hit ? `−${plan.hit}` : "0"}
                  </td>
                  <td
                    className={`tnum py-1.5 pr-3 ${plan.delta_mu >= 0 ? "text-actual" : "text-risk"}`}
                  >
                    {signed(plan.delta_mu, 2)}
                  </td>
                  <td className="tnum py-1.5 pr-3 text-model">{plan.next_xi_mu.toFixed(1)}</td>
                  <td className="py-1.5 pr-3">
                    {plan.moves.length === 0
                      ? "roll"
                      : plan.moves.map((m) => `${m.out_name} → ${m.in_name}`).join(", ")}
                  </td>
                  <td className="py-1.5 pr-3 text-muted">{plan.captain}</td>
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
