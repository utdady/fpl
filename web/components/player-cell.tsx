"use client";

import clsx from "clsx";
import { useRef } from "react";

import { PlayerHover } from "./player-hover";
import { dec, price } from "@/lib/format";
import { useLiveDisplay } from "@/lib/live-context";
import { liveBadgeClass } from "@/lib/live-display";
import type { Position } from "@/lib/types";

export type CellPlayer = {
  id: number;
  name: string;
  pos: Position;
  cost: number | null;
  teamCode: string | null;
  teamId?: number | null;
  mu: number | null;
  sigma: number | null;
  pStart: number | null;
  p10: number | null;
  pts: number | null;
  mins: number | null;
  captain?: boolean;
  vice?: boolean;
  /** Live-season extras, absent for historical seasons. */
  chanceNext?: number | null;
  owned?: number | null;
  epNext?: number | null;
  status?: string | null;
  news?: string | null;
  form?: (number | null)[];
};

/** A blank is a played-zero-minutes slot, the failure mode E009 is about. */
export const isBlank = (p: CellPlayer) => p.mins != null && p.mins === 0;

export type SwapHint = "active" | "valid" | "invalid" | null;

export function PlayerCell({
  player,
  onSelect,
  compact = false,
  selected = false,
  planning = false,
  dragging = false,
  swapHint = null,
  hoverDisabled = false,
  onDragStart,
  onDragEnd,
  onDropPlayer,
}: {
  player: CellPlayer;
  onSelect?: (id: number) => void;
  compact?: boolean;
  selected?: boolean;
  /** Hide live/actual points — show planning xP only. */
  planning?: boolean;
  dragging?: boolean;
  swapHint?: SwapHint;
  hoverDisabled?: boolean;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  onDropPlayer?: () => void;
}) {
  const blank = isBlank(player);
  const scored = player.pts != null;
  const live = useLiveDisplay(player.id, player.teamId);
  const showLive = !planning && live != null;
  const showActual = !planning && !showLive && scored;
  const draggable = Boolean(onDragStart && onDropPlayer);
  const acceptDrop = swapHint === "valid";
  const didDrag = useRef(false);

  return (
    <PlayerHover player={player} disabled={hoverDisabled || dragging}>
      <button
        type="button"
        draggable={draggable}
        onClick={() => {
          if (didDrag.current) {
            didDrag.current = false;
            return;
          }
          onSelect?.(player.id);
        }}
        onDragStart={(e) => {
          if (!draggable) return;
          didDrag.current = true;
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(player.id));
          onDragStart?.();
        }}
        onDragEnd={() => {
          onDragEnd?.();
          // Click often fires after dragend; keep the guard briefly.
          window.setTimeout(() => {
            didDrag.current = false;
          }, 50);
        }}
        onDragOver={(e) => {
          if (!draggable || !acceptDrop) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }}
        onDrop={(e) => {
          if (!draggable || !acceptDrop) return;
          e.preventDefault();
          onDropPlayer?.();
        }}
        className={clsx(
          "group relative flex w-[104px] flex-col items-stretch rounded-lg border bg-panel/80 px-2 pt-2 pb-1.5 text-left transition-all",
          "hover:-translate-y-0.5 hover:border-edge-bright hover:bg-raised",
          blank && !planning && !swapHint ? "border-risk/45" : "border-edge",
          selected && !swapHint && "border-model/70 ring-1 ring-model",
          dragging && "opacity-45",
          swapHint === "active" && "border-model ring-2 ring-model",
          swapHint === "valid" && "border-actual ring-2 ring-actual/70",
          swapHint === "invalid" && "border-risk/60 ring-1 ring-risk/50 opacity-55",
          compact && "w-[92px]",
          draggable && "cursor-grab active:cursor-grabbing",
        )}
      >
        {player.captain && (
          <span
            className="absolute -top-1.5 -left-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-model text-[10px] font-bold text-void"
            title="Captain"
          >
            C
          </span>
        )}
        {player.vice && !player.captain && (
          <span
            className="absolute -top-1.5 -left-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-model/50 text-[9px] font-bold text-model"
            title="Vice captain"
          >
            V
          </span>
        )}

        <div className="flex items-center justify-between gap-1">
          <span className="label-xs truncate">
            {player.teamCode ? `${player.teamCode} · ${player.pos}` : player.pos}
          </span>
          {showLive && (
            <span
              className={clsx(
                "tnum rounded px-1 text-[10px] font-semibold",
                liveBadgeClass(live.tone),
              )}
              title={
                live.minutes == null
                  ? "Fixture not started"
                  : `${live.minutes} minutes · in-play`
              }
            >
              {live.label}
            </span>
          )}
          {showActual && (
            <span
              className={clsx(
                "tnum rounded px-1 text-[10px] font-semibold",
                blank ? "bg-risk/15 text-risk" : "bg-actual/12 text-actual",
              )}
              title={player.mins == null ? undefined : `${player.mins} minutes`}
            >
              {player.pts}
            </span>
          )}
          {planning && (
            <span className="tnum text-[10px] font-semibold text-model" title="V1 expected points">
              xP
            </span>
          )}
        </div>

        <span className="mt-1 truncate text-[12.5px] leading-tight font-medium text-ink">
          {player.name}
        </span>

        <div className="mt-1 flex items-baseline justify-between gap-1">
          <span className="tnum text-[10.5px] text-faint">{price(player.cost)}</span>
          <span
            className="tnum text-[11px] font-semibold text-model"
            title="V1 projected points"
          >
            {dec(player.mu, 1)}
          </span>
        </div>

        {showLive && live.tone === "blank" && (
          <span className="mt-1 text-[9.5px] tracking-wide text-risk uppercase">0 min</span>
        )}
        {!planning && !showLive && blank && (
          <span className="mt-1 text-[9.5px] tracking-wide text-risk uppercase">0 min</span>
        )}
      </button>
    </PlayerHover>
  );
}
