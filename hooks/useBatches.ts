"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Batch, BatchCreate, BatchStatusUpdate, BatchUpdate } from "@/lib/api/types";

export function useBatches() {
  return useQuery({
    queryKey: ["batches"],
    queryFn: () => apiFetch<Batch[]>(endpoints.batches.list),
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BatchCreate) => apiFetch<Batch>(endpoints.batches.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batches"] }),
  });
}

export function useUpdateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchUpdate }) =>
      apiFetch<Batch>(endpoints.batches.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batches"] }),
  });
}

export function useUpdateBatchStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchStatusUpdate }) =>
      apiFetch<Batch>(endpoints.batches.updateStatus(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batches"] }),
  });
}

export function useDeleteBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batches"] }),
  });
}
