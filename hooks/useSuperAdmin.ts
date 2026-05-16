"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
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
  return useQuery({
    queryKey: ["super-admin", "institutions"],
    queryFn: () => apiFetch<Institution[]>(endpoints.superAdmin.institutions),
  });
}

export function useCooperativesGlobal() {
  return useQuery({
    queryKey: ["super-admin", "cooperatives"],
    queryFn: () => apiFetch<Cooperative[]>(endpoints.superAdmin.cooperatives),
  });
}

export function useHierarchyOverview() {
  return useQuery({
    queryKey: ["super-admin", "hierarchy"],
    queryFn: () => apiFetch<HierarchyOverview>(endpoints.superAdmin.hierarchy),
  });
}

export function useSuperAdminOversightCooperatives() {
  return useQuery({
    queryKey: ["super-admin", "oversight", "cooperatives"],
    queryFn: () => apiFetch<CooperativeOversightResponse>(endpoints.superAdmin.oversightCooperatives),
  });
}

export function useCreateInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InstitutionCreate) =>
      apiFetch<Institution>(endpoints.superAdmin.institutions, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
    },
  });
}

export function useUpdateInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InstitutionUpdate }) =>
      apiFetch<Institution>(endpoints.superAdmin.institution(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
    },
  });
}

export function useDeactivateInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Institution>(endpoints.superAdmin.deactivateInstitution(id), { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
    },
  });
}

export function useCreateCooperativeGlobal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CooperativeCreate) =>
      apiFetch<Cooperative>(endpoints.superAdmin.cooperatives, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperatives"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
    },
  });
}

export function useUpdateCooperativeGlobal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CooperativeUpdate }) =>
      apiFetch<Cooperative>(endpoints.superAdmin.cooperative(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["super-admin", "cooperatives"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "hierarchy"] });
      queryClient.invalidateQueries({ queryKey: ["super-admin", "institutions"] });
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
