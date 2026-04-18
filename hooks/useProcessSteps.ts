"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { ProcessStep, ProcessStepCreate, ProcessStepUpdate } from "@/lib/api/types";

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["process-steps"] }),
  });
}

export function useUpdateProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProcessStepUpdate }) =>
      apiFetch<ProcessStep>(endpoints.processSteps.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["process-steps"] }),
  });
}

export function useDeleteProcessStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<ProcessStep>(endpoints.processSteps.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["process-steps"] }),
  });
}
