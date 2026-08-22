"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";

import { StartConfidence } from "./start-confidence";
import { TrackRecord } from "./charts/track-record";
import { Field } from "./ui/stat";
import { dec, pct, price, seasonLabel, signed } from "@/lib/format";
import { useLiveContext, useLiveDisplay } from "@/lib/live-context";
import { liveToneClass } from "@/lib/live-display";
import type { PlayerSeries, Predictions } from "@/lib/types";
import type { CellPlayer } from "./player-cell";

const cache = new Map<string, Promise<Predictions>>();

function loadPredictions(season: string): Promise<Predictions> {
  let pending = cache.get(season);
  if (!pending) {
    pending = fetch(`/data/season/${season}/predictions.json`).then((r) => r.json());
    cache.set(season, pending);
  }
  return pending;
}

export function PlayerDrawer({
  player,
  season,
  gw,
  onClose,
}: {
  player: CellPlayer | null;
  season: string;
  gw: number;
  onClose: () => void;
}) {
  const [series, setSeries] = useState<PlayerSeries | null>(null);
  const liveRaw = useLiveDisplay(player?.id ?? -1, player?.teamId);
  const live = player != null ? liveRaw : null;
  const liveCtx = useLiveContext();
  const liveDelta =
    live?.points != null && player?.mu != null ? live.points - player.mu : null;

  useEffect(() => {
    if (!player) {
      setSeries(null);
      return;
    }
    let live = true;
    loadPredictions(season).then((data) => {
      if (live) setSeries(data.players[String(player.id)] ?? null);
    });
    return () => {
      live = false;
    };
  }, [player, season]);

  const open = player != null;

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-void/75 backdrop-blur-sm" />
        <Dialog.Content className="fixed top-0 right-0 z-50 flex h-full w-full max-w-[440px] flex-col overflow-y-auto border-l border-edge bg-panel shadow-2xl outline-none">
          {player && (
            <>
              <header className="sticky top-0 z-10 border-b border-edge bg-panel/95 px-5 py-4 backdrop-blur">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Dialog.Title className="truncate text-[17px] leading-tight font-semibold">
                      {player.name}
                    </Dialog.Title>
                    <Dialog.Description className="mt-1 text-[11.5px] text-muted">
                      {player.teamCode ?? "—"} · {player.pos} · {price(player.cost)} ·{" "}
                      {seasonLabel(season)} GW{gw}
                    </Dialog.Description>
                  </div>
                  <Dialog.Close className="rounded px-2 py-1 text-[11px] text-muted hover:bg-raised hover:text-ink">
                    Close
                  </Dialog.Close>
                </div>

                <div className="mt-4 flex flex-wrap items-end gap-5">
                  <div>
                    <div className="label-xs">Projected</div>
                    <div className="tnum text-3xl leading-none font-semibold text-model">
                      {dec(player.mu, 2)}
                    </div>
                    <div className="tnum mt-1 text-[11px] text-muted">
                      ± {dec(player.sigma, 2)}
                    </div>
                  </div>
                  {live != null && (
                    <div>
                      <div className="label-xs">Live</div>
                      <div
                        className={`tnum text-3xl leading-none font-semibold ${liveToneClass(live.tone)}`}
                      >
                        {live.label}
                      </div>
                      <div className="tnum mt-1 text-[11px] text-muted">
                        {live.minutes != null ? `${live.minutes}'` : "Not started"}
                        {liveDelta != null ? ` · ${signed(liveDelta, 1)} vs xP` : ""}
                      </div>
                    </div>
                  )}
                  {live == null && player.pts != null && (
                    <div>
                      <div className="label-xs">Actual</div>
                      <div
                        className={`tnum text-3xl leading-none font-semibold ${
                          player.mins === 0 ? "text-risk" : "text-actual"
                        }`}
                      >
                        {player.pts}
                      </div>
                      <div className="tnum mt-1 text-[11px] text-muted">
                        {player.mins ?? "—"} min
                      </div>
                    </div>
                  )}
                  <div className="ml-auto text-right">
                    <div className="label-xs">P(10+)</div>
                    <div className="tnum text-lg leading-none font-semibold text-ink">
                      {pct(player.p10, 1)}
                    </div>
                  </div>
                </div>
                {live != null && (
                  <p className="mt-2 text-[10px] leading-relaxed text-faint">
                    In-play points via FPL live feed
                    {liveCtx?.fetchedAt
                      ? ` · updated ${liveCtx.fetchedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                      : ""}
                    . Not final until the gameweek ends.
                  </p>
                )}
              </header>

              <div className="space-y-6 px-5 py-5">
                <StartConfidence
                  model={player.pStart}
                  fpl={player.chanceNext}
                  p60={null}
                />

                <div>
                  <div className="label-xs mb-2">Season track record</div>
                  {series ? (
                    <TrackRecord series={series} highlight={gw} />
                  ) : (
                    <div className="h-[120px] animate-pulse rounded-lg bg-raised/60" />
                  )}
                </div>

                {series && <SeasonSummary series={series} />}

                <div>
                  <div className="label-xs mb-2">Outcome shape</div>
                  <p className="rounded-lg border border-edge bg-raised/40 p-3 text-[11.5px] leading-relaxed text-muted">
                    The engine runs 2500 simulations per player per gameweek but persists
                    only mu, sigma and P(10+). Drawing a distribution from those three
                    would assert a smooth bell curve the model never claimed, and FPL
                    points are lumpy. A quantile vector from{" "}
                    <span className="font-mono text-faint">capture.py</span> unlocks this
                    panel.
                  </p>
                </div>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SeasonSummary({ series }: { series: PlayerSeries }) {
  const rows = series.gw
    .map((gw, i) => ({
      gw,
      mu: series.mu[i],
      pts: series.pts[i],
      mins: series.min[i],
    }))
    .filter((r) => r.pts != null);

  if (!rows.length) return null;

  const errors = rows.map((r) => (r.pts as number) - (r.mu ?? 0));
  const mae = errors.reduce((s, e) => s + Math.abs(e), 0) / errors.length;
  const bias = errors.reduce((s, e) => s + e, 0) / errors.length;
  const blanks = rows.filter((r) => r.mins === 0).length;
  const total = rows.reduce((s, r) => s + (r.pts as number), 0);

  return (
    <div>
      <div className="label-xs mb-1">Scored gameweeks ({rows.length})</div>
      <Field label="Total points" value={total} tone="actual" />
      <Field label="Mean absolute error" value={dec(mae, 2)} />
      <Field
        label="Bias (actual − projected)"
        value={`${bias >= 0 ? "+" : ""}${dec(bias, 2)}`}
        tone={Math.abs(bias) > 1 ? "risk" : "neutral"}
      />
      <Field
        label="Zero-minute gameweeks"
        value={`${blanks} / ${rows.length}`}
        tone={blanks > rows.length * 0.25 ? "risk" : "neutral"}
      />
    </div>
  );
}
