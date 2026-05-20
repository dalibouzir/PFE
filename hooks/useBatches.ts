"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  Batch,
  BatchCreate,
  BatchMaterialBalance,
  BatchPreHarvestStepStatusesUpdate,
  BatchReferencePreview,
  BatchStartPostHarvestPayload,
  BatchStatusUpdate,
  BatchUpdate,
} from "@/lib/api/types";

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchUpdate }) =>
      apiFetch<Batch>(endpoints.batches.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateBatchStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchStatusUpdate }) =>
      apiFetch<Batch>(endpoints.batches.updateStatus(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDeleteBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.batches.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["process-steps"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useApproveBatchCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<{ batch: Batch }>(endpoints.batches.approveCharge(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useActivatePreHarvest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.activatePreHarvest(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
    },
  });
}

export function useStopPreHarvest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.stopPreHarvest(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
    },
  });
}

export function useCompletePreHarvest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string | null }) =>
      apiFetch<Batch>(endpoints.batches.completePreHarvest(id), {
        method: "POST",
        body: { notes },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["inputs"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useUpdatePreHarvestStepStatuses() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchPreHarvestStepStatusesUpdate }) =>
      apiFetch<Batch>(endpoints.batches.updatePreHarvestStepStatuses(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
    },
  });
}

export function useBatchReferencePreview(productId?: string | null) {
  return useQuery({
    queryKey: ["batch-reference-preview", productId],
    queryFn: () => apiFetch<BatchReferencePreview>(endpoints.batches.previewReference(String(productId))),
    enabled: Boolean(productId),
  });
}

export function useStartPostHarvest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload?: BatchStartPostHarvestPayload | null }) =>
      apiFetch<Batch>(
        payload ? endpoints.batches.startPostHarvestWithStock(id) : endpoints.batches.startPostHarvest(id),
        payload ? { method: "POST", body: payload } : { method: "POST" },
      ),
    onSuccess: (_batch, id) => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["batch-material-balance", id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useCompletePostHarvest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.completePostHarvest(id), { method: "POST" }),
    onSuccess: (_batch, id) => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["batch-material-balance", id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useBatchMaterialBalance(batchId?: string | null) {
  return useQuery({
    queryKey: ["batch-material-balance", batchId],
    queryFn: () => apiFetch<BatchMaterialBalance>(endpoints.batches.materialBalance(String(batchId))),
    enabled: Boolean(batchId),
  });
}
