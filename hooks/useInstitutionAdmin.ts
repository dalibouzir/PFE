"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";
import type {
  Cooperative,
  CooperativeCreate,
  CooperativeUpdate,
  CooperativeUser,
  CooperativeUserCreate,
  CooperativeOversightResponse,
  Institution,
  InstitutionUpdate,
  Member,
} from "@/lib/api/types";

export function useInstitutionAdminInstitution() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "institution"], scope),
    queryFn: () => apiFetch<Institution>(endpoints.institutionAdmin.institution),
  });
}

export function useInstitutionAdminUpdateInstitution() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: InstitutionUpdate) =>
      apiFetch<Institution>(endpoints.institutionAdmin.institution, { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["institution-admin", "institution"], scope) });
    },
  });
}

export function useInstitutionAdminCooperatives() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "cooperatives"], scope),
    queryFn: () => apiFetch<Cooperative[]>(endpoints.institutionAdmin.cooperatives),
  });
}

export function useInstitutionAdminOversightCooperatives() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "oversight", "cooperatives"], scope),
    queryFn: () => apiFetch<CooperativeOversightResponse>(endpoints.institutionAdmin.oversightCooperatives),
  });
}

export function useInstitutionAdminCooperative(cooperativeId: string, enabled = true) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "cooperative"], scope, cooperativeId),
    queryFn: () => apiFetch<Cooperative>(endpoints.institutionAdmin.cooperative(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminCreateCooperative() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: CooperativeCreate) =>
      apiFetch<Cooperative>(endpoints.institutionAdmin.cooperatives, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["institution-admin", "cooperatives"], scope) });
    },
  });
}

export function useInstitutionAdminUpdateCooperative() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CooperativeUpdate }) =>
      apiFetch<Cooperative>(endpoints.institutionAdmin.cooperative(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["institution-admin", "cooperatives"], scope) });
    },
  });
}

export function useInstitutionAdminCooperativeUsers(cooperativeId: string, enabled = true) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "cooperative-users"], scope, cooperativeId),
    queryFn: () => apiFetch<CooperativeUser[]>(endpoints.institutionAdmin.cooperativeUsers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminInsightsCooperativeMembers(cooperativeId: string, enabled = true) {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["institution-admin", "insights", "cooperative-members"], scope, cooperativeId),
    queryFn: () => apiFetch<Member[]>(endpoints.institutionAdmin.insightsCooperativeMembers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminCreateCooperativeUser() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ cooperativeId, payload }: { cooperativeId: string; payload: CooperativeUserCreate }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.cooperativeUsers(cooperativeId), { method: "POST", body: payload }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: scopedQueryKey(["institution-admin", "cooperative-users"], scope, variables.cooperativeId) });
    },
  });
}

export function useInstitutionAdminEnableCooperativeUser() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.enableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: scopedQueryKey(["institution-admin", "cooperative-users"], scope, variables.cooperativeId) });
    },
  });
}

export function useInstitutionAdminDisableCooperativeUser() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.disableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: scopedQueryKey(["institution-admin", "cooperative-users"], scope, variables.cooperativeId) });
    },
  });
}
