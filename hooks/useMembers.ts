"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Member, MemberCreate, MemberUpdate } from "@/lib/api/types";

export function useMembers() {
  return useQuery({
    queryKey: ["members"],
    queryFn: async () => {
      const response = await apiFetch<Member[] | { items: Member[] }>(endpoints.members.list);
      return Array.isArray(response) ? response : response.items;
    },
  });
}

export function useCreateMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MemberCreate) =>
      apiFetch<Member>(endpoints.members.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });
}

export function useUpdateMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: MemberUpdate }) =>
      apiFetch<Member>(endpoints.members.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });
}

export function useDeleteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Member>(endpoints.members.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });
}
