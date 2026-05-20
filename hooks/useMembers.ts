"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Member, MemberCreate, MemberUpdate } from "@/lib/api/types";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";

export function useMembers() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey("members", scope),
    queryFn: async () => {
      const response = await apiFetch<Member[] | { items: Member[] }>(endpoints.members.list);
      return Array.isArray(response) ? response : response.items;
    },
  });
}

export function useCreateMember() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: MemberCreate) =>
      apiFetch<Member>(endpoints.members.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopePrefix("members", scope) }),
  });
}

export function useUpdateMember() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: MemberUpdate }) =>
      apiFetch<Member>(endpoints.members.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopePrefix("members", scope) }),
  });
}

export function useDeleteMember() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Member>(endpoints.members.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scopePrefix("members", scope) }),
  });
}
