"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Input, InputCreate, InputUpdate } from "@/lib/api/types";

export function useInputs() {
  return useQuery({
    queryKey: ["inputs"],
    queryFn: async () => {
      const response = await apiFetch<Input[] | { items: Input[] }>(endpoints.inputs.list);
      return Array.isArray(response) ? response : response.items;
    },
  });
}

export function useCreateInput() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InputCreate) => apiFetch<Input>(endpoints.inputs.list, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inputs"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateInput() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InputUpdate }) =>
      apiFetch<Input>(endpoints.inputs.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inputs"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDeleteInput() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Input>(endpoints.inputs.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inputs"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}


export function useUploadInputJustificatif() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<Input>(endpoints.inputs.justificatif(id), {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inputs"] });
      queryClient.invalidateQueries({ queryKey: ["stock-movements"] });
    },
  });
}
