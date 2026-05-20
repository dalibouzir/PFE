"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Stock, StockAdjustment, StockCreate, StockUpdate } from "@/lib/api/types";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";

export function useStocks() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("stocks", scope),
    queryFn: () => apiFetch<Stock[]>(endpoints.stocks.list),
  });
}

export function useCreateStock() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: StockCreate) => apiFetch<Stock>(endpoints.stocks.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useUpdateStock() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StockUpdate }) =>
      apiFetch<Stock>(endpoints.stocks.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useAdjustStock() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload, direction }: { id: string; payload: StockAdjustment; direction: "increase" | "decrease" }) =>
      apiFetch<Stock>(direction === "increase" ? endpoints.stocks.increase(id) : endpoints.stocks.decrease(id), {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) }),
  });
}

export function useDeleteStock() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.stocks.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}
