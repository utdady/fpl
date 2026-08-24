"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";

import { LoginForm } from "./login-form";
import { useSession } from "@/lib/use-session";

const TABS = [
  { href: "/me/status", label: "Status", match: (p: string) => p === "/me" || p.startsWith("/me/status") },
  { href: "/me/pick-team", label: "Pick Team", match: (p: string) => p.startsWith("/me/pick-team") },
  { href: "/me/transfers", label: "Transfers", match: (p: string) => p.startsWith("/me/transfers") },
  { href: "/me/prices", label: "Price Changes", match: (p: string) => p.startsWith("/me/prices") },
  { href: "/me/injuries", label: "Injuries", match: (p: string) => p.startsWith("/me/injuries") },
  { href: "/me/leagues", label: "Leagues", match: (p: string) => p.startsWith("/me/leagues") },
  { href: "/me/statistics", label: "Statistics", match: (p: string) => p.startsWith("/me/statistics") },
] as const;

export function MeSubnav() {
  const pathname = usePathname();
  const session = useSession();
  const [updateOpen, setUpdateOpen] = useState(false);

  useEffect(() => {
    if (!updateOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setUpdateOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [updateOpen]);

  return (
    <>
      <nav
        className="-mx-5 mb-6 border-y border-edge lg:-mx-8"
        style={{
          background:
            "linear-gradient(90deg, color-mix(in oklab, var(--color-plum) 75%, #1a3a6e), color-mix(in oklab, var(--color-plum-deep) 90%, var(--color-void)))",
        }}
        aria-label="My team"
      >
        <div className="flex items-stretch">
          <ul className="flex min-w-0 flex-1 items-stretch gap-0 overflow-x-auto px-3 lg:px-6">
            {TABS.map((tab) => {
              const active = tab.match(pathname);
              return (
                <li key={tab.href}>
                  <Link
                    href={tab.href}
                    className={clsx(
                      "relative block px-3.5 py-3 text-[13px] whitespace-nowrap transition-colors",
                      active ? "font-semibold text-ink" : "text-ink/75 hover:text-ink",
                    )}
                  >
                    {tab.label}
                    {active && (
                      <span
                        className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-ink"
                        aria-hidden
                      />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>

          {session.loggedIn ? (
            <div className="flex shrink-0 items-center gap-1 border-l border-white/10 px-2 sm:gap-2 sm:px-3 lg:px-4">
              <button
                type="button"
                onClick={() => setUpdateOpen(true)}
                className="rounded-md px-2 py-1.5 text-[12px] whitespace-nowrap text-ink/80 hover:bg-white/10 hover:text-ink"
                title="Paste a fresh oidc.user JSON"
              >
                Update session
              </button>
              <button
                type="button"
                onClick={() => void session.logout()}
                className="rounded-md px-2 py-1.5 text-[12px] whitespace-nowrap text-ink/70 hover:bg-risk/20 hover:text-risk"
              >
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </nav>

      {updateOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-void/75 px-4 py-10 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Update FPL session"
          onClick={(e) => {
            if (e.target === e.currentTarget) setUpdateOpen(false);
          }}
        >
          <LoginForm
            title="Update FPL session"
            submitLabel="Save session"
            onCancel={() => setUpdateOpen(false)}
            onLoggedIn={() => {
              setUpdateOpen(false);
              void session.refresh();
              window.location.reload();
            }}
            className="panel w-full max-w-lg space-y-4 p-5 shadow-xl"
          />
        </div>
      ) : null}
    </>
  );
}
