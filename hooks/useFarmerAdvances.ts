"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";
import type {
  FarmerAdvance,
  FarmerAdvanceCreate,
  FarmerAdvanceFarmerDetailResponse,
  FarmerAdvanceSummaryResponse,
  FarmerAdvanceUpdate,
} from "@/lib/api/types";

type FarmerAdvanceSummaryParams = {
  search?: string;
  sort_by?: "last_modified" | "total_amount";
  order?: "asc" | "desc";
};

function buildSummaryPath(params: FarmerAdvanceSummaryParams) {
  const query = new URLSearchParams();
  if (params.search?.trim()) query.set("search", params.search.trim());
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.order) query.set("order", params.order);
  const queryString = query.toString();
  return queryString ? `${endpoints.farmerAdvances.summary}?${queryString}` : endpoints.farmerAdvances.summary;
}

export function useFarmerAdvanceSummary(params: FarmerAdvanceSummaryParams) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["farmer-advances", "summary"], scope, params),
    queryFn: () => apiFetch<FarmerAdvanceSummaryResponse>(buildSummaryPath(params)),
  });
}

export function useFarmerAdvanceDetail(farmerId: string | null) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["farmer-advances", "detail"], scope, farmerId),
    enabled: Boolean(farmerId),
    queryFn: () => apiFetch<FarmerAdvanceFarmerDetailResponse>(endpoints.farmerAdvances.byFarmer(farmerId as string)),
  });
}

export function useCreateFarmerAdvance() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: FarmerAdvanceCreate) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useUpdateFarmerAdvance() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: FarmerAdvanceUpdate }) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useCancelFarmerAdvance() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.cancel(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useUploadFarmerAdvanceDevis() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<FarmerAdvance>(endpoints.farmerAdvances.devis(id), {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}
