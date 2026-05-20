"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ManualStockMovementCreate, StockMovement, StockMovementFilters } from "@/lib/api/types";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";

function buildStockMovementsPath(filters?: StockMovementFilters) {
  const query = new URLSearchParams();
  if (!filters) return endpoints.stockMovements.list;
  if (filters.date_from) query.set("date_from", filters.date_from);
  if (filters.date_to) query.set("date_to", filters.date_to);
  if (filters.product_id && filters.product_id !== "all") query.set("product_id", filters.product_id);
  if (filters.grade && filters.grade !== "all") query.set("grade", filters.grade);
  if (filters.movement_type && filters.movement_type !== "all") query.set("movement_type", filters.movement_type);
  if (filters.source && filters.source !== "all") query.set("source", filters.source);
  if (filters.batch_reference?.trim()) query.set("batch_reference", filters.batch_reference.trim());
  if (filters.input_reference?.trim()) query.set("input_reference", filters.input_reference.trim());
  if (filters.member_id) query.set("member_id", filters.member_id);
  if (filters.search?.trim()) query.set("search", filters.search.trim());
  if (filters.sort) query.set("sort", filters.sort);
  const qs = query.toString();
  return qs ? `${endpoints.stockMovements.list}?${qs}` : endpoints.stockMovements.list;
}

export function useStockMovements(filters?: StockMovementFilters) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("stock-movements", scope, filters ?? {}),
    queryFn: () => apiFetch<StockMovement[]>(buildStockMovementsPath(filters)),
  });
}

export function useStockMovementDetail(movementId: string | null) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["stock-movements", "detail"], scope, movementId),
    enabled: Boolean(movementId),
    queryFn: () => apiFetch<StockMovement>(endpoints.stockMovements.detail(movementId as string)),
  });
}

export function useCreateManualStockMovement() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: ManualStockMovementCreate) =>
      apiFetch<StockMovement>(endpoints.stockMovements.manualAdjustment, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("stock-movements", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}
