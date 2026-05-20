"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { DashboardResponse } from "@/lib/api/types";
import { scopedQueryKey, useQueryScope } from "@/lib/query/scope";

export function useDashboard() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("dashboard", scope),
    queryFn: () => apiFetch<DashboardResponse>(endpoints.analytics.dashboard),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}
