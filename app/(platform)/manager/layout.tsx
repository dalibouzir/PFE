import { AppShell } from "@/components/app/AppShell";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export default function ManagerLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role={["manager", "owner", "viewer"]}>
      <AppShell role="manager">{children}</AppShell>
    </ProtectedRoute>
  );
}
