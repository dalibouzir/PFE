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

export function useUploadFarmerAdvanceDevis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      const token = typeof window !== "undefined" ? localStorage.getItem("weefarm_token") : null;
      const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";
      const response = await fetch(`${base}${endpoints.farmerAdvances.devis(id)}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });
      if (!response.ok) {
        let message = "Upload devis échoué.";
        try {
          const payload = await response.json();
          message = payload?.detail || message;
        } catch {}
        throw new Error(message);
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
    },
  });
}
