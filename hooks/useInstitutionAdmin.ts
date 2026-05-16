"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
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
  return useQuery({
    queryKey: ["institution-admin", "institution"],
    queryFn: () => apiFetch<Institution>(endpoints.institutionAdmin.institution),
  });
}

export function useInstitutionAdminUpdateInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InstitutionUpdate) =>
      apiFetch<Institution>(endpoints.institutionAdmin.institution, { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "institution"] });
    },
  });
}

export function useInstitutionAdminCooperatives() {
  return useQuery({
    queryKey: ["institution-admin", "cooperatives"],
    queryFn: () => apiFetch<Cooperative[]>(endpoints.institutionAdmin.cooperatives),
  });
}

export function useInstitutionAdminOversightCooperatives() {
  return useQuery({
    queryKey: ["institution-admin", "oversight", "cooperatives"],
    queryFn: () => apiFetch<CooperativeOversightResponse>(endpoints.institutionAdmin.oversightCooperatives),
  });
}

export function useInstitutionAdminCooperative(cooperativeId: string, enabled = true) {
  return useQuery({
    queryKey: ["institution-admin", "cooperative", cooperativeId],
    queryFn: () => apiFetch<Cooperative>(endpoints.institutionAdmin.cooperative(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminCreateCooperative() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CooperativeCreate) =>
      apiFetch<Cooperative>(endpoints.institutionAdmin.cooperatives, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "cooperatives"] });
    },
  });
}

export function useInstitutionAdminUpdateCooperative() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CooperativeUpdate }) =>
      apiFetch<Cooperative>(endpoints.institutionAdmin.cooperative(id), { method: "PATCH", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "cooperatives"] });
    },
  });
}

export function useInstitutionAdminCooperativeUsers(cooperativeId: string, enabled = true) {
  return useQuery({
    queryKey: ["institution-admin", "cooperative-users", cooperativeId],
    queryFn: () => apiFetch<CooperativeUser[]>(endpoints.institutionAdmin.cooperativeUsers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminInsightsCooperativeMembers(cooperativeId: string, enabled = true) {
  return useQuery({
    queryKey: ["institution-admin", "insights", "cooperative-members", cooperativeId],
    queryFn: () => apiFetch<Member[]>(endpoints.institutionAdmin.insightsCooperativeMembers(cooperativeId)),
    enabled: enabled && Boolean(cooperativeId),
  });
}

export function useInstitutionAdminCreateCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cooperativeId, payload }: { cooperativeId: string; payload: CooperativeUserCreate }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.cooperativeUsers(cooperativeId), { method: "POST", body: payload }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}

export function useInstitutionAdminEnableCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.enableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}

export function useInstitutionAdminDisableCooperativeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { cooperativeId: string; userId: string }) =>
      apiFetch<CooperativeUser>(endpoints.institutionAdmin.disableUser(params.userId), { method: "PATCH" }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["institution-admin", "cooperative-users", variables.cooperativeId] });
    },
  });
}
