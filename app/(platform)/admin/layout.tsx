import { AppShell } from "@/components/app/AppShell";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="admin">
      <AppShell role="admin">{children}</AppShell>
    </ProtectedRoute>
  );
}
