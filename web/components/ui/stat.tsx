import clsx from "clsx";

type StatProps = {
  label: string;
  value: React.ReactNode;
  /** Secondary line, e.g. a range or a comparison. */
  note?: React.ReactNode;
  tone?: "model" | "actual" | "risk" | "b0" | "oracle" | "neutral";
  className?: string;
};

const TONE: Record<NonNullable<StatProps["tone"]>, string> = {
  model: "text-model",
  actual: "text-actual",
  risk: "text-risk",
  b0: "text-b0",
  oracle: "text-oracle",
  neutral: "text-ink",
};

export function Stat({ label, value, note, tone = "neutral", className }: StatProps) {
  return (
    <div className={clsx("min-w-0", className)}>
      <div className="label-xs">{label}</div>
      <div className={clsx("tnum mt-1 text-lg leading-none font-semibold", TONE[tone])}>
        {value}
      </div>
      {note && <div className="tnum mt-1 text-[11px] text-muted">{note}</div>}
    </div>
  );
}

export function StatRow({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap gap-x-8 gap-y-4">{children}</div>;
}

/** Small tabular key/value line used inside the player drawer. */
export function Field({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  tone?: NonNullable<StatProps["tone"]>;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-edge/60 py-1.5 last:border-0">
      <span className="text-[11.5px] text-muted">{label}</span>
      <span className={clsx("tnum text-[12px] font-medium", TONE[tone])}>{value}</span>
    </div>
  );
}
