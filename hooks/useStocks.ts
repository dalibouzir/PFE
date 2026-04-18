"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Stock, StockAdjustment, StockCreate, StockUpdate } from "@/lib/api/types";

export function useStocks() {
  return useQuery({
    queryKey: ["stocks"],
    queryFn: () => apiFetch<Stock[]>(endpoints.stocks.list),
  });
}

export function useCreateStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StockCreate) => apiFetch<Stock>(endpoints.stocks.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocks"] }),
  });
}

export function useUpdateStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StockUpdate }) =>
      apiFetch<Stock>(endpoints.stocks.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocks"] }),
  });
}

export function useAdjustStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload, direction }: { id: string; payload: StockAdjustment; direction: "increase" | "decrease" }) =>
      apiFetch<Stock>(direction === "increase" ? endpoints.stocks.increase(id) : endpoints.stocks.decrease(id), {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocks"] }),
  });
}

export function useDeleteStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Stock>(endpoints.stocks.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["stocks"] }),
  });
}
