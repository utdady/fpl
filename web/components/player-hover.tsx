"use client";

import * as HoverCard from "@radix-ui/react-hover-card";

import { calibratedStart, dec, pct, price } from "@/lib/format";
import { SNAPSHOT_DAY } from "@/lib/snapshot";
import type { CellPlayer } from "./player-cell";

/**
 * The gameweek card. Deliberately holds nothing bigger than a bar: if it needed
 * a legend it would have failed at its job, which is to stop you clicking.
 */
export function PlayerHover({
  player,
  children,
}: {
  player: CellPlayer;
  children: React.ReactNode;
}) {
  const observed = calibratedStart(player.pStart);
  const overconfident =
    player.pStart != null && observed != null && player.pStart - observed > 0.08;
  // Snapshot fields are live-season only. A fit player has chanceNext null rather
  // than absent, so undefined is what separates the live pool from a record.
  const fromSnapshot =
    player.chanceNext !== undefined ||
    player.owned !== undefined ||
    player.epNext !== undefined;

  return (
    <HoverCard.Root openDelay={250} closeDelay={80}>
      <HoverCard.Trigger asChild>{children}</HoverCard.Trigger>
      <HoverCard.Portal>
        <HoverCard.Content
          side="right"
          align="start"
          sideOffset={10}
          className="z-50 w-[276px] rounded-xl border border-edge-bright bg-panel/98 p-3.5 shadow-2xl backdrop-blur data-[state=open]:animate-in data-[state=open]:fade-in-0"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold text-ink">{player.name}</div>
              <div className="mt-0.5 text-[10.5px] text-muted">
                {player.teamCode ?? "—"} · {player.pos} · {price(player.cost)}
              </div>
            </div>
            <div className="text-right">
              <div className="tnum text-xl leading-none font-semibold text-model">
                {dec(player.mu, 2)}
              </div>
              <div className="tnum mt-0.5 text-[10px] text-faint">
                ± {dec(player.sigma, 2)}
              </div>
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            <Bar label="V1 p(start)" value={player.pStart} color="var(--color-model)" />
            {player.chanceNext != null && (
              <Bar
                label="FPL availability"
                value={player.chanceNext / 100}
                color="var(--color-ink)"
              />
            )}
            <Bar
              label="Historical at this level"
              value={observed}
              color="var(--color-risk)"
            />
          </div>

          {fromSnapshot && SNAPSHOT_DAY && (
            <p className="mt-1.5 text-[9.5px] leading-relaxed text-faint">
              Price, ownership and availability are the {SNAPSHOT_DAY} snapshot. No news
              flag here means none at that date, not none now.
            </p>
          )}

          {overconfident && (
            <p className="mt-2 text-[10px] leading-relaxed text-risk/85">
              Model is {pct(player.pStart! - observed!, 0)} above the four-season start
              rate at this confidence.
            </p>
          )}

          <div className="mt-3 flex items-center justify-between border-t border-edge pt-2.5">
            <Mini label="P(10+)" value={pct(player.p10, 1)} />
            {player.epNext != null && <Mini label="FPL ep" value={dec(player.epNext, 1)} />}
            {player.owned != null && <Mini label="Owned" value={`${player.owned}%`} />}
            {player.pts != null && (
              <Mini
                label="Actual"
                value={String(player.pts)}
                tone={player.mins === 0 ? "text-risk" : "text-actual"}
              />
            )}
          </div>

          {player.news && (
            <p className="mt-2.5 rounded bg-risk/10 px-2 py-1.5 text-[10px] leading-relaxed text-risk">
              {player.news}
            </p>
          )}

          <HoverCard.Arrow className="fill-[var(--color-edge-bright)]" />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}

function Bar({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null | undefined;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[126px] shrink-0 text-[10px] text-muted">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-raised">
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.round((value ?? 0) * 100)}%`, background: color }}
        />
      </div>
      <span className="tnum w-8 shrink-0 text-right text-[10px]">{pct(value, 0)}</span>
    </div>
  );
}

function Mini({
  label,
  value,
  tone = "text-ink",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div>
      <div className="label-xs">{label}</div>
      <div className={`tnum mt-0.5 text-[12px] font-medium ${tone}`}>{value}</div>
    </div>
  );
}
