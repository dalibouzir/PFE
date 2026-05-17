"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ProcessStep, ProcessStepCompletePayload, ProcessStepCreate, ProcessStepUpdate } from "@/lib/api/types";

export function useProcessSteps() {
  return useQuery({
    queryKey: ["process-steps"],
    queryFn: () => apiFetch<ProcessStep[]>(endpoints.processSteps.list),
  });
}

export function useCreateProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProcessStepCreate) => apiFetch<ProcessStep>(endpoints.processSteps.list, { method: "POST", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: ["process-steps"] });
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["batch-material-balance", step.batch_id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useUpdateProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessStepUpdate }) =>
      apiFetch<ProcessStep>(endpoints.processSteps.update(id), { method: "PATCH", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: ["process-steps"] });
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["batch-material-balance", step.batch_id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useCompleteProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessStepCompletePayload }) =>
      apiFetch<ProcessStep>(endpoints.processSteps.complete(id), { method: "POST", body: payload }),
    onSuccess: (step) => {
      queryClient.invalidateQueries({ queryKey: ["process-steps"] });
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["batch-material-balance", step.batch_id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useDeleteProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.processSteps.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["process-steps"] });
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}
