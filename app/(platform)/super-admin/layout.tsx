import { AppShell } from "@/components/app/AppShell";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role={["super_admin", "admin"]}>
      <AppShell role="super_admin">{children}</AppShell>
    </ProtectedRoute>
  );
}
