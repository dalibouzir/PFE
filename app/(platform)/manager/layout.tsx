import { AppShell } from "@/components/app/AppShell";

export default function ManagerLayout({ children }: { children: React.ReactNode }) {
  return <AppShell role="manager">{children}</AppShell>;
}
