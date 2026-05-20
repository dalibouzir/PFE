"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";
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
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("batches", scope),
    queryFn: () => apiFetch<Batch[]>(endpoints.batches.list),
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: BatchCreate) => apiFetch<Batch>(endpoints.batches.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useUpdateBatch() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchUpdate }) =>
      apiFetch<Batch>(endpoints.batches.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useUpdateBatchStatus() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchStatusUpdate }) =>
      apiFetch<Batch>(endpoints.batches.updateStatus(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useDeleteBatch() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.batches.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("process-steps", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
    },
  });
}

export function useApproveBatchCharge() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<{ batch: Batch }>(endpoints.batches.approveCharge(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("farmer-advances", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("treasury", scope) });
    },
  });
}

export function useActivatePreHarvest() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.activatePreHarvest(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
    },
  });
}

export function useStopPreHarvest() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.stopPreHarvest(id), { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
    },
  });
}

export function useCompletePreHarvest() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string | null }) =>
      apiFetch<Batch>(endpoints.batches.completePreHarvest(id), {
        method: "POST",
        body: { notes },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("inputs", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useUpdatePreHarvestStepStatuses() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BatchPreHarvestStepStatusesUpdate }) =>
      apiFetch<Batch>(endpoints.batches.updatePreHarvestStepStatuses(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
    },
  });
}

export function useBatchReferencePreview(productId?: string | null) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("batch-reference-preview", scope, productId),
    queryFn: () => apiFetch<BatchReferencePreview>(endpoints.batches.previewReference(String(productId))),
    enabled: Boolean(productId),
  });
}

export function useStartPostHarvest() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload?: BatchStartPostHarvestPayload | null }) =>
      apiFetch<Batch>(
        payload ? endpoints.batches.startPostHarvestWithStock(id) : endpoints.batches.startPostHarvest(id),
        payload ? { method: "POST", body: payload } : { method: "POST" },
      ),
    onSuccess: (_batch, id) => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopedQueryKey("batch-material-balance", scope, id) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useCompletePostHarvest() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Batch>(endpoints.batches.completePostHarvest(id), { method: "POST" }),
    onSuccess: (_batch, id) => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopedQueryKey("batch-material-balance", scope, id) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useBatchMaterialBalance(batchId?: string | null) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("batch-material-balance", scope, batchId),
    queryFn: () => apiFetch<BatchMaterialBalance>(endpoints.batches.materialBalance(String(batchId))),
    enabled: Boolean(batchId),
  });
}
