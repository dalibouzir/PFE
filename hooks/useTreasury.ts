"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  TreasuryStats,
  TreasuryTransaction,
  TreasuryTransactionCreate,
  TreasuryTransactionUpdate,
} from "@/lib/api/types";

type TreasuryFilters = {
  type?: "all" | "income" | "expense";
  source_type?: string;
  search?: string;
  sort?: "asc" | "desc";
};

function buildTreasuryPath(filters: TreasuryFilters) {
  const query = new URLSearchParams();
  if (filters.type && filters.type !== "all") query.set("type", filters.type);
  if (filters.source_type && filters.source_type !== "all") query.set("source_type", filters.source_type);
  if (filters.search?.trim()) query.set("search", filters.search.trim());
  if (filters.sort) query.set("sort", filters.sort);
  const queryString = query.toString();
  return queryString ? `${endpoints.treasury.list}?${queryString}` : endpoints.treasury.list;
}

export function useTreasuryTransactions(filters: TreasuryFilters) {
  return useQuery({
    queryKey: ["treasury", "list", filters],
    queryFn: () => apiFetch<TreasuryTransaction[]>(buildTreasuryPath(filters)),
  });
}

export function useTreasuryStats() {
  return useQuery({
    queryKey: ["treasury", "stats"],
    queryFn: () => apiFetch<TreasuryStats>(endpoints.treasury.stats),
  });
}

export function useCreateTreasuryTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TreasuryTransactionCreate) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useUpdateTreasuryTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TreasuryTransactionUpdate }) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useCancelTreasuryTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.cancel(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}
