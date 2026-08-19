import { Section } from "@/components/ui/section";

/**
 * Phase 6. The numbers this surface needs exist only as CLI output today, so
 * the page states what must be persisted rather than inventing a chart.
 */
const MISSING = [
  {
    field: "Leave-one-out delta per player",
    where: "engine/audit.py",
    unlocks: "Ranked bar chart of what each player is worth to the objective",
    evidence: "E001 recorded Enzo 2.87, Gabriel 2.83, Guehi 1.94 as CLI output only.",
  },
  {
    field: "Lock / exclude counterfactuals",
    where: "engine/audit.py",
    unlocks: "What forcing a player in or out costs the objective",
    evidence: "E001 measured the Haaland lock at 4.86 but did not write it to a record.",
  },
  {
    field: "mu component breakdown",
    where: "engine/capture.py",
    unlocks: "Contribution waterfall: appearance, goals, assists, CS, DC, saves, bonus",
    evidence: "project.py computes the components and capture.py keeps only their sum.",
  },
  {
    field: "Simulation quantiles",
    where: "engine/capture.py",
    unlocks: "Honest outcome distribution instead of a fabricated bell curve",
    evidence: "2500 sims per player per gameweek collapse to mu, sigma and P(10+).",
  },
  {
    field: "P(0 points)",
    where: "engine/capture.py",
    unlocks: "Boom-or-bust quadrant against positional peers",
    evidence:
      "1 - p_start is not the same quantity: a nailed starter who blanks is exactly the E009 failure mode.",
  },
  {
    field: "Per-strategy squads",
    where: "engine/capture.py",
    unlocks: "Safe / balanced / aggressive toggle, and the fifteen with its bench",
    evidence: "Only the balanced solve is captured, and squad membership is not stored.",
  },
];

export default function AuditPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Audit</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          Why each player is in the eleven, priced in objective points rather than
          opinion. This surface is not built yet, and the reason is data rather than
          design.
        </p>
      </div>

      <Section
        title="Six fields stand between here and this surface"
        subtitle="None of them change a projection. All are persistence and diagnostics, deferred until after GW1 so the production freeze holds through the 2026-08-21 deadline."
        source="docs/LAB_LOG.md"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-[12px]">
            <thead>
              <tr className="border-b border-edge">
                <th className="label-xs py-2 pr-4 text-left font-normal">Field</th>
                <th className="label-xs py-2 pr-4 text-left font-normal">Lives in</th>
                <th className="label-xs py-2 pr-4 text-left font-normal">Unlocks</th>
              </tr>
            </thead>
            <tbody>
              {MISSING.map((row) => (
                <tr key={row.field} className="border-b border-edge/40 align-top">
                  <td className="py-2.5 pr-4 font-medium text-ink">{row.field}</td>
                  <td className="py-2.5 pr-4 font-mono text-[11px] text-b0">{row.where}</td>
                  <td className="py-2.5 pr-4 text-muted">
                    {row.unlocks}
                    <p className="mt-1 text-[11px] text-faint">{row.evidence}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
