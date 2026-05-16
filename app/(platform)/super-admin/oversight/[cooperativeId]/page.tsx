"use client";

import { useParams } from "next/navigation";
import { CooperativeOversightDetail } from "@/components/oversight/CooperativeOversightDashboard";
import { useSuperAdminOversightCooperatives } from "@/hooks/useSuperAdmin";

export default function SuperAdminOversightDetailPage() {
  const params = useParams<{ cooperativeId: string }>();
  const cooperativeId = String(params.cooperativeId || "");
  const query = useSuperAdminOversightCooperatives();
  return (
    <CooperativeOversightDetail
      scope="super_admin"
      cooperativeId={cooperativeId}
      data={query.data}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
    />
  );
}
