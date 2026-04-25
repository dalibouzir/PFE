"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
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
  return useQuery({
    queryKey: ["farmer-advances", "summary", params],
    queryFn: () => apiFetch<FarmerAdvanceSummaryResponse>(buildSummaryPath(params)),
  });
}

export function useFarmerAdvanceDetail(farmerId: string | null) {
  return useQuery({
    queryKey: ["farmer-advances", "detail", farmerId],
    enabled: Boolean(farmerId),
    queryFn: () => apiFetch<FarmerAdvanceFarmerDetailResponse>(endpoints.farmerAdvances.byFarmer(farmerId as string)),
  });
}

export function useCreateFarmerAdvance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FarmerAdvanceCreate) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useUpdateFarmerAdvance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: FarmerAdvanceUpdate }) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useCancelFarmerAdvance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<FarmerAdvance>(endpoints.farmerAdvances.cancel(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}
