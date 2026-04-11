import { AppShell } from "@/components/app/AppShell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AppShell role="admin">{children}</AppShell>;
}
