"use client";

import { useParams } from "next/navigation";
import { CooperativeOversightDetail } from "@/components/oversight/CooperativeOversightDashboard";
import { useInstitutionAdminOversightCooperatives } from "@/hooks/useInstitutionAdmin";

export default function InstitutionAdminOversightDetailPage() {
  const params = useParams<{ cooperativeId: string }>();
  const cooperativeId = String(params.cooperativeId || "");
  const query = useInstitutionAdminOversightCooperatives();
  return (
    <CooperativeOversightDetail
      scope="institution_admin"
      cooperativeId={cooperativeId}
      data={query.data}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
    />
  );
}
