import { MeSubnav } from "@/components/me-subnav";

export default function MeLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <MeSubnav />
      {children}
    </div>
  );
}
