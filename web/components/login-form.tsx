"use client";

import { useMemo, useState } from "react";

import { accountJson } from "@/lib/fpl-account";
import { notifySession } from "@/lib/use-session";

const CONSOLE_SNIPPET = `copy(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith('oidc.user:'))))`;

function inspectPaste(raw: string): {
  ok: boolean;
  hint: string;
  hasAccess: boolean;
  hasRefresh: boolean;
} {
  const trimmed = raw.trim();
  if (!trimmed) return { ok: false, hint: "", hasAccess: false, hasRefresh: false };

  if (!trimmed.startsWith("{")) {
    return {
      ok: false,
      hint: "Paste must start with { — you likely copied only the refresh_token. Use the Console snippet below.",
      hasAccess: false,
      hasRefresh: false,
    };
  }

  try {
    const obj = JSON.parse(trimmed) as Record<string, unknown>;
    const hasAccess = typeof obj.access_token === "string" && obj.access_token.length > 20;
    const hasRefresh = typeof obj.refresh_token === "string" && obj.refresh_token.length > 20;
    if (!hasAccess) {
      return {
        ok: false,
        hint: "JSON is missing access_token. Copy the full oidc.user value, not a partial field.",
        hasAccess,
        hasRefresh,
      };
    }
    return {
      ok: true,
      hint: hasRefresh
        ? "Looks good — access_token and refresh_token found."
        : "access_token found (no refresh_token — session will be short-lived).",
      hasAccess,
      hasRefresh,
    };
  } catch {
    return {
      ok: false,
      hint: "Not valid JSON yet. Paste the whole oidc.user string from the Console.",
      hasAccess: false,
      hasRefresh: false,
    };
  }
}

export function LoginForm({
  onLoggedIn,
  onCancel,
  title = "Sign in to FPL",
  submitLabel = "Sign in",
  className = "panel mx-auto max-w-lg space-y-4 p-5",
}: {
  onLoggedIn: () => void;
  onCancel?: () => void;
  title?: string;
  submitLabel?: string;
  className?: string;
}) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(true);

  const inspection = useMemo(() => inspectPaste(token), [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!inspection.ok) {
      setError(inspection.hint || "Paste the full oidc.user JSON first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await accountJson("/api/account/login", {
        method: "POST",
        body: JSON.stringify({ refreshToken: token }),
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      notifySession();
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className={className}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            Paste the <span className="text-ink">full</span>{" "}
            <code className="text-ink">oidc.user</code> JSON (starts with{" "}
            <code className="text-ink">{"{"}</code>). A bare refresh token will not
            work — FPL rotates it in the background.
          </p>
        </div>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="shrink-0 rounded-md px-2 py-1 text-[12px] text-muted hover:text-ink"
            aria-label="Close"
          >
            ✕
          </button>
        ) : null}
      </div>

      <label className="block">
        <span className="label-xs">oidc.user JSON</span>
        <textarea
          required
          value={token}
          onChange={(e) => setToken(e.target.value)}
          rows={6}
          placeholder='{"id_token":"...","session_state":"...","access_token":"...","refresh_token":"...",...}'
          className="mt-1.5 w-full rounded-md border border-edge bg-raised px-2.5 py-2 font-mono text-[11px] outline-none focus:border-edge-bright"
        />
      </label>

      {token.trim() && (
        <p className={`text-[11.5px] ${inspection.ok ? "text-actual" : "text-oracle"}`}>
          {inspection.hint}
        </p>
      )}

      <button
        type="button"
        onClick={() => setShowHelp(!showHelp)}
        className="text-[11.5px] text-muted hover:text-ink"
      >
        {showHelp ? "Hide steps" : "Show steps"}
      </button>

      {showHelp && (
        <div className="space-y-2 rounded-md border border-edge bg-void/40 p-3 text-[11.5px] leading-relaxed text-muted">
          <p className="font-medium text-ink">Do this exactly:</p>
          <ol className="list-decimal space-y-1.5 pl-4">
            <li>
              Open{" "}
              <a
                href="https://fantasy.premierleague.com/"
                target="_blank"
                rel="noreferrer"
                className="text-model"
              >
                fantasy.premierleague.com
              </a>{" "}
              and make sure you are logged in.
            </li>
            <li>
              Hard-refresh that tab: <code className="text-ink">Ctrl+Shift+R</code> (gets a
              fresh token pair).
            </li>
            <li>
              F12 → <span className="text-ink">Console</span>. If needed, type{" "}
              <code className="text-ink">allow pasting</code> and press Enter.
            </li>
            <li>Paste and run:</li>
          </ol>
          <pre className="overflow-x-auto rounded-md border border-edge bg-panel p-2 font-mono text-[10px] text-faint">
            {CONSOLE_SNIPPET}
          </pre>
          <ol className="list-decimal space-y-1.5 pl-4" start={5}>
            <li>
              Immediately come back here and Ctrl+V. The paste must start with{" "}
              <code className="text-ink">{"{"}</code> and include{" "}
              <code className="text-ink">access_token</code>.
            </li>
          </ol>
          <p className="text-oracle">
            Do not copy only <code className="text-ink">.refresh_token</code>. Do not wait —
            FPL renews and rotates tokens every few minutes while the tab is open.
          </p>
        </div>
      )}

      {error && <p className="text-[12px] text-risk">{error}</p>}

      <div className="flex flex-wrap gap-2">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-edge px-3 py-2 text-[13px] text-muted hover:text-ink"
          >
            Cancel
          </button>
        ) : null}
        <button
          type="submit"
          disabled={busy || !inspection.ok}
          className="min-w-[8rem] flex-1 rounded-md bg-model/15 px-3 py-2 text-[13px] font-medium text-model disabled:opacity-50"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
