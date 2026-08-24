"use client";

import { LoginForm } from "./login-form";
import { useSession } from "@/lib/use-session";

/** Gates My Team pages behind FPL sign-in. */
export function MeGate({ children }: { children: React.ReactNode }) {
  const session = useSession();

  if (session.loading) {
    return <p className="text-[12px] text-muted">Checking FPL session…</p>;
  }
  if (!session.loggedIn) {
    return <LoginForm onLoggedIn={() => void session.refresh()} />;
  }
  return <>{children}</>;
}
