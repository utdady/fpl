import clsx from "clsx";

import { Caveats } from "./caveat";

type SectionProps = {
  title: string;
  /** Names the oracle, the slice, or the units. Sits directly under the title. */
  subtitle?: string;
  /** Which artifact the numbers came from. */
  source?: string;
  caveats?: string[];
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
};

export function Section({
  title,
  subtitle,
  source,
  caveats,
  actions,
  className,
  children,
}: SectionProps) {
  return (
    <section className={clsx("panel flex flex-col p-5", className)}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold tracking-tight text-ink">{title}</h2>
          {subtitle && (
            <p className="mt-1 max-w-2xl text-[11.5px] leading-relaxed text-muted">{subtitle}</p>
          )}
        </div>
        {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
      </div>

      <div className="mt-4 flex-1">{children}</div>

      {(caveats?.length || source) && (
        <div className="mt-4 border-t border-edge pt-3">
          {caveats?.length ? <Caveats items={caveats} /> : null}
          {source && (
            <p className="mt-2 font-mono text-[10px] text-faint">
              source: <span className="text-muted">{source}</span>
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-[11px] text-muted">
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ background: item.color }}
            aria-hidden
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
