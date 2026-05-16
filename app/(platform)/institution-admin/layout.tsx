import { AppShell } from "@/components/app/AppShell";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

export default function InstitutionAdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="institution_admin">
      <AppShell role="institution_admin">{children}</AppShell>
    </ProtectedRoute>
  );
}
