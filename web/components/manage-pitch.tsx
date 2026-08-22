"use client";

import { PlayerCell, type CellPlayer } from "./player-cell";
import { PitchMarkings } from "./pitch";
import { POSITIONS } from "@/lib/format";

export function ManagePitch({
  xi,
  bench,
  selected,
  onSelect,
}: {
  xi: CellPlayer[];
  bench: CellPlayer[];
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  const rows = POSITIONS.map((pos) => xi.filter((p) => p.pos === pos)).filter(
    (row) => row.length > 0,
  );

  return (
    <>
      <div className="relative overflow-hidden rounded-xl border border-edge">
        <PitchMarkings />
        <div className="relative flex flex-col gap-5 px-4 py-7">
          {rows.map((row, i) => (
            <div key={i} className="flex flex-wrap justify-center gap-2.5">
              {row.map((player) => (
                <PlayerCell
                  key={player.id}
                  player={player}
                  selected={selected === player.id}
                  onSelect={onSelect}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {bench.length > 0 && (
        <div className="mt-3">
          <div className="label-xs mb-2">Bench order</div>
          <div className="flex flex-wrap gap-2">
            {bench.map((player) => (
              <PlayerCell
                key={player.id}
                player={player}
                compact
                selected={selected === player.id}
                onSelect={onSelect}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
