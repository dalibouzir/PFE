"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Field, FieldCreate, FieldUpdate } from "@/lib/api/types";

export function useFields() {
  return useQuery({
    queryKey: ["fields"],
    queryFn: () => apiFetch<Field[]>(endpoints.fields.list),
  });
}

export function useCreateField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FieldCreate) => apiFetch<Field>(endpoints.fields.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fields"] }),
  });
}

export function useUpdateField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: FieldUpdate }) =>
      apiFetch<Field>(endpoints.fields.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fields"] }),
  });
}

export function useDeleteField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Field>(endpoints.fields.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["fields"] }),
  });
}
