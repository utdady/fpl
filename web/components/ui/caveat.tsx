"use client";

import { useState } from "react";

/**
 * Caveats arrive inside the exported JSON rather than being written here, so a
 * chart cannot be rendered without the warning its source data carries.
 */
export function Caveats({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[10.5px] tracking-wide text-risk/85 transition-colors hover:text-risk"
      >
        <span
          className="inline-block h-1.5 w-1.5 rounded-full bg-risk"
          aria-hidden
        />
        {items.length} caveat{items.length > 1 ? "s" : ""}
        <span className="text-faint">{open ? "hide" : "show"}</span>
      </button>

      {open && (
        <ul className="mt-2 space-y-2">
          {items.map((text) => (
            <li
              key={text}
              className="border-l-2 border-risk/40 pl-3 text-[11px] leading-relaxed text-muted"
            >
              {text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Inline warning used where a single number needs qualifying in place. */
export function Warn({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-risk/12 px-1.5 py-0.5 text-[10.5px] text-risk">{children}</span>
  );
}
