import { notFound } from "next/navigation";

import { DecisionChart } from "@/components/charts/decision-chart";
import { DriftChart } from "@/components/charts/drift-chart";
import { LeakageStrip } from "@/components/charts/leakage-strip";
import { PanelTable } from "@/components/charts/panel-table";
import { RegretChart, RegretShare } from "@/components/charts/regret-chart";
import { Reliability } from "@/components/charts/reliability";
import { SeasonTabs } from "@/components/gw-strip";
import { Legend, Section } from "@/components/ui/section";
import { Stat, StatRow } from "@/components/ui/stat";
import {
  getCompare,
  getDecisions,
  getLabSeasons,
  getLeakage,
  getMinutes,
  getPanel,
  getScores,
} from "@/lib/data";
import { dec, seasonLabel, signed } from "@/lib/format";

export async function generateStaticParams() {
  const seasons = await getLabSeasons();
  return seasons.map((season) => ({ season }));
}

export default async function LabPage({ params }: { params: Promise<{ season: string }> }) {
  const { season } = await params;
  const seasons = await getLabSeasons();
  if (!seasons.includes(season)) notFound();

  const [compare, decisions, leakage, minutes, scores, panel] = await Promise.all([
    getCompare(season),
    getDecisions(season),
    getLeakage(season),
    getMinutes(season),
    getScores(season),
    getPanel(),
  ]);

  const flaggedGws = leakage.gws.filter((g) => g.flag).map((g) => g.gw);
  const clean = decisions.gws.filter((d) => d.status === "clean");
  const fit = minutes.fits.find((f) => f.split === "all");
  const tail = minutes.buckets.find((b) => b.split === "all" && b.bucket === "0.90-1.00");
  const seasonRow = panel.seasons.find((s) => s.season === season);

  const cleanDelta =
    clean.length > 0
      ? clean.reduce((sum, d) => sum + ((d.v1_gw1 ?? 0) - (d.v1 ?? 0)), 0) / clean.length
      : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Lab · {seasonLabel(season)}
          </h1>
          <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
            Out-of-sample evaluation of the frozen V1 model against three baselines,
            reconstructed as-of-T with a strict information cutoff.
          </p>
        </div>
        <SeasonTabs seasons={seasons} current={season} basePath="lab" />
      </div>

      <Section title="Headline" source={`records/historical/${season}/`}>
        <StatRow>
          <Stat
            label="V1 XI + captain"
            value={dec(compare.summary.B3_v1?.xi, 1)}
            tone="model"
            note={`vs B1 ${dec(compare.summary.B1_season_pts?.xi, 1)} · B2 ${dec(
              compare.summary.B2_pp90?.xi,
              1,
            )}`}
          />
          <Stat
            label="Player MAE"
            value={dec(compare.summary.B3_v1?.mae, 3)}
            note={`Spearman ${dec(compare.summary.B3_v1?.spearman, 3)}`}
          />
          <Stat
            label="B0 flagged weeks"
            value={`${leakage.flagged}/${leakage.total}`}
            tone="b0"
            note="possible post-deadline information"
          />
          <Stat
            label="Start rate at p ≥ 0.90"
            value={`${dec(tail?.start_pct, 1)}%`}
            tone="risk"
            note={`n=${tail?.n} · fitted ${dec(fit?.p90_fitted, 1)}%`}
          />
          <Stat
            label="XI zero-minute slots"
            value={`${dec(seasonRow?.xi_zero_min.all?.pct, 1)}%`}
            tone="risk"
            note={`${seasonRow?.xi_zero_min.all?.zero}/${seasonRow?.xi_zero_min.all?.slots} slots`}
          />
        </StatRow>
      </Section>

      <Section
        title="Decision quality by gameweek"
        subtitle="XI plus captain, actual points. Shaded weeks are those where B0 tripped the pre-registered leakage flag; on those weeks B0's line is not a baseline."
        source={`records/historical/${season}/b0_b3_comparison.csv`}
        caveats={compare.caveats}
        actions={
          <Legend
            items={[
              { color: "var(--color-model)", label: "V1" },
              { color: "var(--color-b0)", label: "B0 xP" },
              { color: "var(--color-oracle)", label: "Oracle" },
            ]}
          />
        }
      >
        <DecisionChart compare={compare} decisions={decisions.gws} flaggedGws={flaggedGws} />
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section
          title="Is B0 a predictor or an oracle?"
          subtitle={`Spearman between Vaastav xP and actual points, per gameweek. ${leakage.flagged} of ${leakage.total} weeks exceed the threshold.`}
          source={`records/historical/${season}/b0_leakage.csv`}
          caveats={leakage.caveats}
        >
          <LeakageStrip leakage={leakage} />
        </Section>

        <Section
          title="Playing-time calibration"
          subtitle="Claimed p_start against observed start rate. Points below the diagonal are overconfidence; circle area is bucket size."
          source={`records/historical/${season}/minutes_cal.csv`}
          caveats={minutes.caveats}
        >
          <Reliability minutes={minutes} />
        </Section>
      </div>

      <Section
        title="Where the points went"
        subtitle={`Nested hindsight regret against a ${decisions.oracle}. R_total = R_squad + R_XI + R_cap = P(oracle) − P(V1 realized).`}
        source={`records/historical/${season}/decision_gw.csv`}
        caveats={decisions.caveats}
      >
        <RegretChart decisions={decisions.gws} />
        <RegretShare decisions={decisions.gws} />
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section
          title="Error across the season"
          subtitle="Late-season improvement is expected: the snapshot accumulates current-season minutes. It is not evidence that preseason V1 is strong."
          source={`records/historical/${season}/scores.csv`}
        >
          <DriftChart scores={scores} />
        </Section>

        <Section
          title="Horizon counterfactual"
          subtitle="V1_GW1 is the same mu solved with a next-gameweek objective instead of six."
          source={`records/historical/${season}/decision_gw.csv`}
        >
          <StatRow>
            <Stat
              label="V1_GW1 − V1, clean weeks"
              value={signed(cleanDelta, 2)}
              tone={(cleanDelta ?? 0) < 0 ? "risk" : "neutral"}
              note={`n=${clean.length} clean of ${decisions.gws.length}`}
            />
          </StatRow>
          <p className="mt-4 border-l-2 border-edge-bright pl-3 text-[11.5px] leading-relaxed text-muted">
            The sign is inconsistent across the four seasons, including −0.48 in 2022/23.
            That inconsistency, not the size of any single season, is why the horizon
            objective was shelved rather than changed.
          </p>
        </Section>
      </div>

      <Section
        title="Four-season robustness panel"
        subtitle="E013. Every gate is evaluated per season rather than averaged, because 2024/25's XI zero-minute rate is an outlier and not the low end of a range."
        source="scripts/export_ui.py from records/historical/*"
        caveats={panel.caveats}
      >
        <PanelTable panel={panel} current={season} />
      </Section>
    </div>
  );
}
