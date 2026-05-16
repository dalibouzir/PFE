"use client";

import { CooperativeOversightOverview } from "@/components/oversight/CooperativeOversightDashboard";
import { useInstitutions, useSuperAdminOversightCooperatives } from "@/hooks/useSuperAdmin";

export default function SuperAdminOversightPage() {
  const query = useSuperAdminOversightCooperatives();
  const institutionsQuery = useInstitutions();

  return (
    <CooperativeOversightOverview
      scope="super_admin"
      data={query.data}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      institutionsCount={(institutionsQuery.data || []).length}
    />
  );
}
