"use client";

import { useState } from "react";

import { PlayerCell, type CellPlayer, type SwapHint } from "./player-cell";
import { PitchMarkings } from "./pitch";
import { POSITIONS } from "@/lib/format";

export function ManagePitch({
  xi,
  bench,
  selected,
  onSelect,
  onSwap,
  canSwap,
  planning = false,
  /** Show full squad by position (no bench rail) — for Transfers. */
  squadBoard = false,
}: {
  xi: CellPlayer[];
  bench: CellPlayer[];
  selected: number | null;
  onSelect: (id: number) => void;
  onSwap?: (a: number, b: number) => void;
  canSwap?: (a: number, b: number) => boolean;
  planning?: boolean;
  squadBoard?: boolean;
}) {
  const [dragId, setDragId] = useState<number | null>(null);
  const squad = squadBoard ? [...xi, ...bench] : xi;
  const rows = POSITIONS.map((pos) => squad.filter((p) => p.pos === pos)).filter(
    (row) => row.length > 0,
  );
  const showBench = !squadBoard && bench.length > 0;

  function hintFor(id: number): SwapHint {
    // Drag-swap hints only while dragging (or tap-swap when canSwap is wired).
    const sourceId = dragId ?? (canSwap ? selected : null);
    if (sourceId == null) return null;
    if (id === sourceId) return "active";
    if (canSwap?.(sourceId, id)) return "valid";
    return "invalid";
  }

  function handleDrop(targetId: number) {
    if (dragId == null || dragId === targetId) {
      setDragId(null);
      return;
    }
    if (canSwap && !canSwap(dragId, targetId)) {
      setDragId(null);
      return;
    }
    onSwap?.(dragId, targetId);
    setDragId(null);
  }

  function renderCell(player: CellPlayer, compact = false) {
    const hint = hintFor(player.id);
    const dragEnabled = Boolean(onSwap);
    return (
      <PlayerCell
        key={player.id}
        player={player}
        compact={compact}
        selected={selected === player.id}
        onSelect={onSelect}
        planning={planning}
        dragging={dragId === player.id}
        swapHint={hint}
        hoverDisabled={dragId != null}
        onDragStart={dragEnabled ? () => setDragId(player.id) : undefined}
        onDragEnd={dragEnabled ? () => setDragId(null) : undefined}
        onDropPlayer={dragEnabled ? () => handleDrop(player.id) : undefined}
      />
    );
  }

  return (
    <div
      className={
        showBench
          ? "grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_6.75rem] sm:items-start"
          : undefined
      }
    >
      <div className="relative min-w-0 overflow-hidden rounded-xl border border-edge">
        <PitchMarkings />
        <div className="relative flex flex-col gap-5 px-4 py-7">
          {rows.map((row, i) => (
            <div key={i} className="flex flex-wrap justify-center gap-2.5">
              {row.map((player) => renderCell(player))}
            </div>
          ))}
        </div>
      </div>

      {showBench && (
        <aside className="flex flex-col rounded-xl border border-edge bg-panel/40 px-2.5 pt-2.5 pb-1.5 sm:w-[6.75rem]">
          <div className="label-xs mb-2 shrink-0">Bench</div>
          <div className="flex flex-col items-center gap-2.5">
            {bench.map((player) => (
              <div key={player.id} className="flex flex-col items-center">
                {renderCell(player, true)}
              </div>
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}
