"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  FarmerChargesResponse,
  GlobalCharge,
  GlobalChargeCreate,
  GlobalChargeUpdate,
  Member,
  Parcel,
  ParcelCreate,
  ParcelUpdate,
  PreHarvestStep,
  PreHarvestStepUpdate,
} from "@/lib/api/types";

export function useFarmers() {
  return useQuery({
    queryKey: ["farmers"],
    queryFn: () => apiFetch<Member[]>(endpoints.farmers.list),
  });
}

export function useParcels(memberId?: string | null) {
  return useQuery({
    queryKey: ["parcels", memberId ?? "all"],
    queryFn: () => apiFetch<Parcel[]>(memberId ? endpoints.farmers.parcels(memberId) : endpoints.parcels.list),
  });
}

export function useCreateParcel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ParcelCreate) => apiFetch<Parcel>(endpoints.parcels.list, { method: "POST", body: payload }),
    onSuccess: (_created, payload) => {
      queryClient.invalidateQueries({ queryKey: ["parcels"] });
      queryClient.invalidateQueries({ queryKey: ["parcels", payload.farmer_id] });
      queryClient.invalidateQueries({ queryKey: ["farmers"] });
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });
}

export function useUpdateParcel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ParcelUpdate }) =>
      apiFetch<Parcel>(endpoints.parcels.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parcels"] });
      queryClient.invalidateQueries({ queryKey: ["farmers"] });
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });
}

export function useDeleteParcel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.parcels.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["parcels"] });
      queryClient.invalidateQueries({ queryKey: ["farmers"] });
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });
}

export function usePreHarvestSteps(parcelId?: string | null) {
  return useQuery({
    queryKey: ["preharvest-steps", parcelId ?? ""],
    queryFn: () => apiFetch<PreHarvestStep[]>(endpoints.parcels.preHarvest(parcelId as string)),
    enabled: Boolean(parcelId),
  });
}

export function useUpdatePreHarvestStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ parcelId, stepId, payload }: { parcelId: string; stepId: string; payload: PreHarvestStepUpdate }) =>
      apiFetch<PreHarvestStep>(endpoints.preHarvestEvents.update(stepId, parcelId), {
        method: "PUT",
        body: payload,
      }),
    onSuccess: (_updated, args) => {
      queryClient.invalidateQueries({ queryKey: ["preharvest-steps", args.parcelId] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useCompletePreHarvestStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ parcelId, stepId }: { parcelId: string; stepId: string }) =>
      apiFetch<PreHarvestStep>(endpoints.preHarvestEvents.complete(stepId, parcelId), { method: "POST" }),
    onSuccess: (_updated, args) => {
      queryClient.invalidateQueries({ queryKey: ["preharvest-steps", args.parcelId] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useFarmerCharges(farmerId?: string | null) {
  return useQuery({
    queryKey: ["farmer-charges", farmerId ?? ""],
    queryFn: () => apiFetch<FarmerChargesResponse>(endpoints.farmers.charges(farmerId as string)),
    enabled: Boolean(farmerId),
  });
}

export function useCreateGlobalCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GlobalChargeCreate) =>
      apiFetch<GlobalCharge>(endpoints.charges.list, { method: "POST", body: payload }),
    onSuccess: (_created, payload) => {
      queryClient.invalidateQueries({ queryKey: ["farmer-charges", payload.farmer_id] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
    },
  });
}

export function useUpdateGlobalCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: GlobalChargeUpdate }) =>
      apiFetch<GlobalCharge>(endpoints.charges.update(id), { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-charges"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
    },
  });
}

export function useDeleteGlobalCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(endpoints.charges.delete(id), { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["farmer-charges"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
      queryClient.invalidateQueries({ queryKey: ["farmer-advances"] });
    },
  });
}
