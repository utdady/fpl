import Link from "next/link";
import { notFound } from "next/navigation";

import { GwStrip, SeasonTabs } from "@/components/gw-strip";
import { Pitch, XiList } from "@/components/pitch";
import { StrategyBoard } from "@/components/strategy-board";
import { Section } from "@/components/ui/section";
import { Stat, StatRow } from "@/components/ui/stat";
import { getAllSeasons, getDecisions, getLabSeasons, getManifest, getStrategies } from "@/lib/data";
import { dec, formation, seasonLabel, signed } from "@/lib/format";
import { buildXi } from "@/lib/squad";

export async function generateStaticParams() {
  const seasons = await getLabSeasons();
  return seasons.flatMap((season) =>
    Array.from({ length: 38 }, (_, i) => ({ season, gw: String(i + 1) })),
  );
}

export default async function SquadPage({
  params,
}: {
  params: Promise<{ season: string; gw: string }>;
}) {
          const { season, gw: gwParam } = await params;
          const gw = Number(gwParam);
          const manifest = await getManifest();
          const labSeasons = await getLabSeasons();
          const seasons = await getAllSeasons();
          const meta = manifest.seasons.find((s) => s.season === season);
  // Range-check before touching any season file: a gameweek that never existed is
  // a 404, not an empty board, and the guard keeps the on-demand render reading
  // nothing but the manifest.
  if (!meta || !Number.isFinite(gw) || gw < 1 || gw > meta.gws) notFound();

  // A season can exist in the manifest without an eleven: the live season is a
  // prediction pool only. That is a state to explain, not a missing page.
  if (!labSeasons.includes(season)) {
    let strategies = null;
    try {
      strategies = await getStrategies(season);
    } catch {
      strategies = null;
    }
    if (strategies) {
      return (
        <div className="space-y-5">
          <Header season={season} seasons={seasons} />
          <StrategyBoard season={season} data={strategies} />
        </div>
      );
    }
    return (
      <div className="space-y-5">
        <Header season={season} seasons={seasons} />
        <Section
          title={`No eleven for ${seasonLabel(season)}`}
          subtitle="The XI board reads the decision decomposition, which exists only for scored seasons."
          source={`records/historical/${season}/ (absent)`}
          caveats={[manifest.caveats.live_pool]}
        >
          <p className="text-[12px] leading-relaxed text-muted">
            The frozen projections for this season are on the{" "}
            <Link href="/" className="text-model underline decoration-model/40 underline-offset-2">
              prediction pool
            </Link>
            . Pick a scored season above for an eleven.
          </p>
        </Section>
      </div>
    );
  }

  const [{ v1, b0, caveats, availableGws }, decisions] = await Promise.all([
    buildXi(season, gw),
    getDecisions(season),
  ]);

  const summary = decisions.gws.find((d) => d.gw === gw);
  const blanks = v1.filter((p) => p.mins === 0).length;
  const captain = v1.find((p) => p.captain);

  if (!v1.length) {
    return (
      <div className="space-y-5">
        <Header season={season} seasons={seasons} />
        <GwStrip season={season} current={gw} gws={availableGws} decisions={decisions.gws} />
        <Section
          title={`No eleven recorded for GW${gw}`}
          subtitle="2022/23 GW7 has no Vaastav actuals, so the decomposition skips it."
          source={`records/historical/${season}/decision_decomp.csv`}
        >
          <p className="text-[12px] text-muted">Pick another gameweek above.</p>
        </Section>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Header season={season} seasons={seasons} />

      <GwStrip season={season} current={gw} gws={availableGws} decisions={decisions.gws} />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Section
          title={`V1 eleven — ${seasonLabel(season)} GW${gw}`}
          subtitle={`Formation ${formation(v1.map((p) => p.pos))}. Captain ${
            captain?.name ?? "none"
          }. Click a player for the full outlook.`}
          source={`records/historical/${season}/decision_decomp.csv`}
          caveats={caveats}
          actions={
            summary && (
              <span
                className={`rounded px-2 py-0.5 font-mono text-[10px] ${
                  summary.status === "clean"
                    ? "bg-raised text-muted"
                    : "bg-b0/15 text-b0"
                }`}
                title="Structural evaluation status. Never set from model scores."
              >
                {summary.status}
                {summary.flags.length > 0 && ` · ${summary.flags.join(" ")}`}
              </span>
            )
          }
        >
          <Pitch players={v1} season={season} gw={gw} />
        </Section>

        <div className="space-y-5">
          <Section
            title="Gameweek result"
            subtitle={summary ? `Against a ${decisions.oracle}.` : undefined}
            caveats={summary ? decisions.caveats : undefined}
            source={`records/historical/${season}/decision_gw.csv`}
          >
            <StatRow>
              <Stat
                label="V1 XI + captain"
                value={dec(summary?.v1, 0)}
                tone="model"
                note={`${blanks} zero-minute slot${blanks === 1 ? "" : "s"}`}
              />
              <Stat
                label="B0 xP eleven"
                value={dec(summary?.b0, 0)}
                tone="b0"
                note={summary ? `gap ${signed(summary.vs_b0, 0)}` : undefined}
              />
              <Stat label="Oracle" value={dec(summary?.oracle, 0)} tone="oracle" />
            </StatRow>

            {summary && (
              <div className="mt-5">
                <div className="label-xs mb-2">Hindsight regret split</div>
                <RegretBar
                  squad={summary.r_squad ?? 0}
                  xi={summary.r_xi ?? 0}
                  cap={summary.r_cap ?? 0}
                />
              </div>
            )}
          </Section>

          <Section
            title="Eleven vs eleven"
            subtitle={`Overlap ${summary?.xi_overlap ?? "—"} of 11.`}
            source={`records/historical/${season}/decision_decomp.csv`}
          >
            <div className="grid grid-cols-2 gap-4">
              <XiList players={v1} title="V1" tone="model" />
              <XiList players={b0} title="B0 xP" tone="b0" />
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}

function Header({ season, seasons }: { season: string; seasons: string[] }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">XI board</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          The frozen V1 eleven for every scored gameweek, beside the official-xP eleven
          and the hindsight oracle. The live season is a re-solved fifteen (safe /
          balanced / aggressive) from the cached snapshot; historical boards remain an
          eleven because the bench was never persisted.
        </p>
      </div>
      <SeasonTabs seasons={seasons} current={season} basePath="squad" />
    </div>
  );
}

function RegretBar({ squad, xi, cap }: { squad: number; xi: number; cap: number }) {
  const total = squad + xi + cap;
  if (total <= 0) {
    return <p className="text-[11px] text-muted">No regret: V1 matched the oracle.</p>;
  }
  const parts = [
    { label: "squad", value: squad, color: "var(--color-oracle)" },
    { label: "XI", value: xi, color: "var(--color-b0)" },
    { label: "captain", value: cap, color: "var(--color-risk)" },
  ];

  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-raised">
        {parts.map((p) => (
          <div
            key={p.label}
            style={{ width: `${(p.value / total) * 100}%`, background: p.color }}
            title={`${p.label}: ${p.value.toFixed(1)} pts`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {parts.map((p) => (
          <span key={p.label} className="tnum text-[10.5px] text-muted">
            <span
              className="mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle"
              style={{ background: p.color }}
            />
            {p.label} {((p.value / total) * 100).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}
