"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ProcessStep, ProcessStepCompletePayload, ProcessStepCreate, ProcessStepUpdate } from "@/lib/api/types";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";

export function useProcessSteps() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("process-steps", scope),
    queryFn: () => apiFetch<ProcessStep[]>(endpoints.processSteps.list),
  });
}

export function useCreateProcessStep() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: ProcessStepCreate) => apiFetch<ProcessStep>(endpoints.processSteps.list, { method: "POST", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("process-steps", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopedQueryKey("batch-material-balance", scope, step.batch_id) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useUpdateProcessStep() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessStepUpdate }) =>
      apiFetch<ProcessStep>(endpoints.processSteps.update(id), { method: "PATCH", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("process-steps", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopedQueryKey("batch-material-balance", scope, step.batch_id) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useCompleteProcessStep() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessStepCompletePayload }) =>
      apiFetch<ProcessStep>(endpoints.processSteps.complete(id), { method: "POST", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("process-steps", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopedQueryKey("batch-material-balance", scope, step.batch_id) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}

export function useDeleteProcessStep() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.processSteps.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix("process-steps", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("batches", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("dashboard", scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix("stocks", scope) });
    },
  });
}
