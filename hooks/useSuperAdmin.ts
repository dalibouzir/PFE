"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { scopePrefix, scopedQueryKey, useQueryScope } from "@/lib/query/scope";
import type {
  Cooperative,
  CooperativeUser,
  CooperativeUserCreate,
  CooperativeCreate,
  CooperativeUpdate,
  HierarchyOverview,
  Institution,
  InstitutionCreate,
  InstitutionUpdate,
  CooperativeOversightResponse,
  InstitutionAdminCreate,
  InstitutionAdminUser,
  Member,
} from "@/lib/api/types";

export function useInstitutions() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["super-admin", "institutions"], scope),
    queryFn: () => apiFetch<Institution[]>(endpoints.superAdmin.institutions),
  });
}

export function useCooperativesGlobal() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["super-admin", "cooperatives"], scope),
    queryFn: () => apiFetch<Cooperative[]>(endpoints.superAdmin.cooperatives),
  });
}

export function useHierarchyOverview() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["super-admin", "hierarchy"], scope),
    queryFn: () => apiFetch<HierarchyOverview>(endpoints.superAdmin.hierarchy),
  });
}

export function useSuperAdminOversightCooperatives() {
  const scope = useQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["super-admin", "oversight", "cooperatives"], scope),
    queryFn: () => apiFetch<CooperativeOversightResponse>(endpoints.superAdmin.oversightCooperatives),
  });
}

export function useCreateInstitution() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: InstitutionCreate) =>
      apiFetch<Institution>(endpoints.superAdmin.institutions, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "institutions"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "hierarchy"], scope) });
    },
  });
}

export function useUpdateInstitution() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InstitutionUpdate }) =>
      apiFetch<Institution>(endpoints.superAdmin.institution(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "institutions"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "hierarchy"], scope) });
    },
  });
}

export function useDeactivateInstitution() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Institution>(endpoints.superAdmin.deactivateInstitution(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "institutions"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "hierarchy"], scope) });
    },
  });
}

export function useCreateCooperativeGlobal() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: (payload: CooperativeCreate) =>
      apiFetch<Cooperative>(endpoints.superAdmin.cooperatives, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "cooperatives"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "hierarchy"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "institutions"], scope) });
    },
  });
}

export function useUpdateCooperativeGlobal() {
  const queryClient = useQueryClient();
  const scope = useQueryScope();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CooperativeUpdate }) =>
      apiFetch<Cooperative>(endpoints.superAdmin.cooperative(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "cooperatives"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "hierarchy"], scope) });
      queryClient.invalidateQueries({ queryKey: scopePrefix(["super-admin", "institutions"], scope) });
    },
  });
}

export function useAssignCooperativeToInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cooperativeId, institutionId }: { cooperativeId: string; institutionId: string }) =>
      apiFetch<Cooperative>(endpoints.superAdmin.assignInstitution(cooperativeId), {
        method: "PATCH",
        body: { institution_id: institutionId },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperatives"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
    },
  });
}

export function useMakeCooperativeIndependent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cooperativeId: string) =>
      apiFetch<Cooperative>(endpoints.superAdmin.makeIndependent(cooperativeId), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperatives"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
    },
  });
}

export function useDeactivateCooperative() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Cooperative>(endpoints.superAdmin.deactivateCooperative(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperatives"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
    },
  });
}

export function useSuperAdminCooperativeUsers(cooperativeId: string, enabled = true) {
  return useQuery({
    queryKey: ["super-admin", "cooperative-users", cooperativeId],
    queryFn: () => apiFetch<CooperativeUser[]>(endpoints.superAdmin.cooperativeUsers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useSuperAdminInsightsCooperativeMembers(cooperativeId: string, enabled = true) {
  return useQuery({
    queryKey: ["super-admin", "insights", "cooperative-members", cooperativeId],
    queryFn: () => apiFetch<Member[]>(endpoints.superAdmin.insightsCooperativeMembers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useSuperAdminCreateCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cooperativeId, payload }: { cooperativeId: string; payload: CooperativeUserCreate }) =>
      apiFetch<CooperativeUser>(endpoints.superAdmin.cooperativeUsers(cooperativeId), { method: "POST", body: payload }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}

export function useSuperAdminEnableCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.superAdmin.enableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}

export function useSuperAdminDisableCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.superAdmin.disableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}

export function useInstitutionAdmins(institutionId: string, enabled = true) {
  return useQuery({
    queryKey: ["super-admin", "institution-admins", institutionId],
    queryFn: () => apiFetch<InstitutionAdminUser[]>(endpoints.superAdmin.institutionAdmins(institutionId)),
    enabled: enabled && Boolean(institutionId),
  });
}

export function useCreateInstitutionAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ institutionId, payload }: { institutionId: string; payload: InstitutionAdminCreate }) =>
      apiFetch<InstitutionAdminUser>(endpoints.superAdmin.institutionAdmins(institutionId), { method: "POST", body: payload }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institution-admins", variables.institutionId] });
    },
  });
}

export function useEnableInstitutionAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { institutionId: string; userId: string }) =>
      apiFetch<InstitutionAdminUser>(endpoints.superAdmin.enableInstitutionAdmin(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institution-admins", variables.institutionId] });
    },
  });
}

export function useDisableInstitutionAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { institutionId: string; userId: string }) =>
      apiFetch<InstitutionAdminUser>(endpoints.superAdmin.disableInstitutionAdmin(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institution-admins", variables.institutionId] });
    },
  });
}
