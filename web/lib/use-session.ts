"use client";

import { useCallback, useEffect, useState } from "react";

import {
  readAccountSession,
  type AccountSession,
} from "@/lib/fpl-account";

export const SESSION_EVENT = "fpl-session";

export function notifySession() {
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function useSession() {
  const [state, setState] = useState<AccountSession & { loading: boolean }>({
    loading: true,
    loggedIn: false,
    entryId: null,
    name: null,
    playerName: null,
  });

  const refresh = useCallback(async () => {
    const session = await readAccountSession();
    setState({ ...session, loading: false });
  }, []);

  useEffect(() => {
    void refresh();
    const onChange = () => void refresh();
    window.addEventListener(SESSION_EVENT, onChange);
    return () => window.removeEventListener(SESSION_EVENT, onChange);
  }, [refresh]);

  const logout = useCallback(async () => {
    await fetch("/api/account/logout", { method: "POST" });
    notifySession();
    await refresh();
  }, [refresh]);

  return { ...state, refresh, logout };
}
