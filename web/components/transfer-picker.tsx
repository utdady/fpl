"use client";

import {
  upcomingFixturesForTeam,
  type BootstrapElement,
  type BootstrapTeam,
  type FplApiFixture,
} from "@/lib/fpl-account";
import { dec, difficultyColor, price } from "@/lib/format";

function num(value: string | number | null | undefined, digits = 1) {
  if (value == null || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function int(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return String(value);
}

type PickerRow = {
  el: BootstrapElement;
  mu: number;
  pStart: number | null;
};

export function TransferPickerPanel({
  outgoingName,
  rows,
  query,
  onQueryChange,
  onClose,
  onPick,
  fixtures,
  teams,
  fromGw,
}: {
  outgoingName: string;
  rows: PickerRow[];
  query: string;
  onQueryChange: (q: string) => void;
  onClose: () => void;
  onPick: (el: BootstrapElement) => void;
  fixtures: FplApiFixture[];
  teams: Map<number, BootstrapTeam>;
  fromGw: number;
}) {
  const teamCodes = new Map(
    [...teams.entries()].map(([id, t]) => [id, t.short_name] as const),
  );
  const gwCols = [fromGw, fromGw + 1, fromGw + 2];

  return (
    <>
      <button
        type="button"
        aria-label="Close transfer picker"
        className="fixed inset-0 z-[44] bg-void/60 md:bg-transparent md:pointer-events-none"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Replace ${outgoingName}`}
        className="fixed z-[45] flex flex-col overflow-hidden border-edge bg-panel shadow-2xl outline-none pointer-events-auto inset-x-0 bottom-0 max-h-[85vh] rounded-t-xl border-t md:inset-y-0 md:left-0 md:right-[440px] md:bottom-auto md:max-h-none md:h-full md:w-auto md:rounded-none md:border-t-0 md:border-r"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-edge px-4 py-3">
          <div className="min-w-0">
            <div className="text-[14px] font-medium">Replace {outgoingName}</div>
            <p className="mt-0.5 text-[11px] text-faint">
              Sorted by V1 μ · same position · scroll sideways for more stats
            </p>
          </div>
          <button
            type="button"
            className="shrink-0 text-[11px] text-muted hover:text-ink"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <div className="shrink-0 px-4 py-3">
          <input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search"
            autoFocus
            className="w-full rounded-md border border-edge bg-raised px-2.5 py-1.5 text-[13px] outline-none focus:border-edge-bright"
          />
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-max min-w-full border-separate border-spacing-0 text-left text-[11.5px]">
            <thead className="sticky top-0 z-[1]">
              <tr className="bg-panel">
                <th className="sticky left-0 z-[2] bg-panel px-3 py-2 font-medium text-faint">
                  Player
                </th>
                <th className="sticky left-[9.5rem] z-[2] bg-panel px-2 py-2 text-right font-medium text-faint">
                  μ
                </th>
                <Th>Form</Th>
                <Th>Price</Th>
                <Th>Sel%</Th>
                <Th>{fromGw > 1 ? `GW${fromGw - 1}` : "GW pts"}</Th>
                <Th>Total</Th>
                <Th>ICT</Th>
                <Th>Inf</Th>
                <Th>Cre</Th>
                <Th>Thr</Th>
                <Th>TIn</Th>
                <Th>TOut</Th>
                <Th>Bonus</Th>
                {gwCols.map((g) => (
                  <Th key={g}>GW{g}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ el, mu, pStart }) => {
                const fixtures3 = upcomingFixturesForTeam(
                  fixtures,
                  el.team,
                  teamCodes,
                  fromGw,
                  3,
                );
                return (
                  <tr
                    key={el.id}
                    className="group cursor-pointer hover:bg-raised/80"
                    onClick={() => onPick(el)}
                  >
                    <td className="sticky left-0 z-[1] w-[9.5rem] max-w-[9.5rem] bg-panel px-3 py-1.5 group-hover:bg-raised/80">
                      <div className="truncate text-[12.5px] font-medium text-ink">
                        {el.web_name}
                      </div>
                      <div className="truncate text-[10px] text-faint">
                        {teamCodes.get(el.team) ?? "—"}
                        {el.status !== "a" ? ` · ${el.status}` : ""}
                        {pStart != null ? ` · ${Math.round(pStart * 100)}%` : ""}
                      </div>
                    </td>
                    <td className="sticky left-[9.5rem] z-[1] bg-panel px-2 py-1.5 text-right group-hover:bg-raised/80">
                      <span className="tnum font-semibold text-model">
                        {dec(mu < 0 ? null : mu, 1)}
                      </span>
                    </td>
                    <Td>{num(el.form, 1)}</Td>
                    <Td>{price(el.now_cost)}</Td>
                    <Td>{el.selected_by_percent ? `${el.selected_by_percent}%` : "—"}</Td>
                    <Td>{int(el.event_points)}</Td>
                    <Td>{int(el.total_points)}</Td>
                    <Td>{num(el.ict_index, 1)}</Td>
                    <Td>{num(el.influence, 1)}</Td>
                    <Td>{num(el.creativity, 1)}</Td>
                    <Td>{num(el.threat, 1)}</Td>
                    <Td>{int(el.transfers_in_event)}</Td>
                    <Td>{int(el.transfers_out_event)}</Td>
                    <Td>{int(el.bonus)}</Td>
                    {fixtures3.map((fx) => (
                      <td key={fx.gw} className="px-1.5 py-1.5">
                        <span
                          className="tnum inline-block min-w-[3.25rem] rounded px-1.5 py-0.5 text-center text-[10.5px] font-medium text-ink"
                          style={{
                            background: `color-mix(in oklab, ${difficultyColor(fx.fdr)} 28%, transparent)`,
                            boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${difficultyColor(fx.fdr)} 55%, transparent)`,
                          }}
                          title={
                            fx.opponentCode === "—"
                              ? `GW${fx.gw} blank`
                              : `GW${fx.gw} ${fx.home ? "vs" : "@"} ${fx.opponentCode} · FDR ${fx.fdr}`
                          }
                        >
                          {fx.opponentCode === "—"
                            ? "—"
                            : `${fx.opponentCode}${fx.home ? " (H)" : " (A)"}`}
                        </span>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="whitespace-nowrap px-2 py-2 text-right font-medium text-faint">
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td className="tnum whitespace-nowrap px-2 py-1.5 text-right text-muted">{children}</td>
  );
}
