"use client";

import { CooperativeOversightOverview } from "@/components/oversight/CooperativeOversightDashboard";
import {
  useInstitutionAdminInstitution,
  useInstitutionAdminOversightCooperatives,
} from "@/hooks/useInstitutionAdmin";

export default function InstitutionAdminOversightPage() {
  const query = useInstitutionAdminOversightCooperatives();
  const institutionQuery = useInstitutionAdminInstitution();

  return (
    <CooperativeOversightOverview
      scope="institution_admin"
      data={query.data}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      institutionName={institutionQuery.data?.name || null}
    />
  );
}
