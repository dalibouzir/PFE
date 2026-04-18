"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  AdminUser,
  Cooperative,
  CooperativeCreate,
  ManagerCreate,
} from "@/lib/api/types";

export function useCooperatives() {
  return useQuery({
    queryKey: ["admin", "cooperatives"],
    queryFn: () => apiFetch<Cooperative[]>(endpoints.admin.cooperatives),
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<AdminUser[]>(endpoints.admin.users),
  });
}

export function useCreateCooperative() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CooperativeCreate) =>
      apiFetch<Cooperative>(endpoints.admin.cooperatives, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "cooperatives"] }),
  });
}

export function useCreateManager() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ManagerCreate) =>
      apiFetch<AdminUser>(endpoints.admin.managers, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useDisableUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<AdminUser>(endpoints.admin.disableUser(userId), { method: "PATCH" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useEnableUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<AdminUser>(endpoints.admin.enableUser(userId), { method: "PATCH" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch<AdminUser>(endpoints.admin.deleteUser(userId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}
