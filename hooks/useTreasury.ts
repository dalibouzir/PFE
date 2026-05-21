"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";
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
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["treasury", "list"], scope, filters),
    queryFn: () => apiFetch<TreasuryTransaction[]>(buildTreasuryPath(filters)),
  });
}

export function useTreasuryStats() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["treasury", "stats"], scope),
    queryFn: () => apiFetch<TreasuryStats>(endpoints.treasury.stats),
  });
}

export function useCreateTreasuryTransaction() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: TreasuryTransactionCreate) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useUpdateTreasuryTransaction() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TreasuryTransactionUpdate }) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useCancelTreasuryTransaction() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<TreasuryTransaction>(endpoints.treasury.cancel(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useUploadTreasuryJustificatif() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<TreasuryTransaction>(endpoints.treasury.justificatif(id), {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: (updated) => {
      queryClient.setQueriesData<TreasuryTransaction[]>(
        { queryKey: scopePrefix(["treasury", "list"], scope) },
        (current) => current?.map((item) => (item.id === updated.id ? updated : item)),
      );
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
    },
  });
}
