"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type {
  CatalogProduct,
  CatalogProductCreate,
  CatalogProductUpdate,
  CommercialInvoice,
  CommercialInvoiceStats,
  CommercialOrder,
  CommercialOrderIntake,
  CommercialOrderStats,
  CommercialOrderStatus,
  CommercialOrderStatusUpdate,
} from "@/lib/api/types";

export function useCatalogProducts() {
  return useQuery({
    queryKey: ["commercial", "catalog"],
    queryFn: () => apiFetch<CatalogProduct[]>(endpoints.commercial.catalog),
  });
}

export function useCreateCatalogProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CatalogProductCreate) =>
      apiFetch<CatalogProduct>(endpoints.commercial.catalog, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useUpdateCatalogProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CatalogProductUpdate }) =>
      apiFetch<CatalogProduct>(`${endpoints.commercial.catalog}/${id}`, {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] }),
  });
}

export function useSetCatalogProductStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: "active" | "hidden" }) =>
      apiFetch<CatalogProduct>(endpoints.commercial.catalogStatus(id, status), {
        method: "PATCH",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] }),
  });
}

export function useDeleteCatalogProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<CatalogProduct>(endpoints.commercial.catalogDelete(id), {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] });
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
    },
  });
}

export function useCommercialOrders(params?: { status?: CommercialOrderStatus | "all"; search?: string }) {
  return useQuery({
    queryKey: ["commercial", "orders", params ?? {}],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params?.status && params.status !== "all") query.set("status", params.status);
      if (params?.search?.trim()) query.set("search", params.search.trim());
      const qs = query.toString();
      const path = qs ? `${endpoints.commercial.orders}?${qs}` : endpoints.commercial.orders;
      return apiFetch<CommercialOrder[]>(path);
    },
  });
}

export function useCommercialOrderStats() {
  return useQuery({
    queryKey: ["commercial", "orders", "stats"],
    queryFn: () => apiFetch<CommercialOrderStats>(endpoints.commercial.orderStats),
  });
}

export function useIntakeCommercialOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CommercialOrderIntake) =>
      apiFetch<CommercialOrder>(endpoints.commercial.orders, { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commercial", "orders"] });
      queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] });
      queryClient.invalidateQueries({ queryKey: ["commercial", "invoices"] });
    },
  });
}

export function useUpdateCommercialOrderStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CommercialOrderStatusUpdate }) =>
      apiFetch<CommercialOrder>(endpoints.commercial.orderStatus(id), {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commercial", "orders"] });
      queryClient.invalidateQueries({ queryKey: ["commercial", "orders", "stats"] });
      queryClient.invalidateQueries({ queryKey: ["commercial", "catalog"] });
      queryClient.invalidateQueries({ queryKey: ["commercial", "invoices"] });
      queryClient.invalidateQueries({ queryKey: ["treasury"] });
    },
  });
}

export function useCommercialInvoices(params?: { status?: "all" | "pending" | "paid"; search?: string }) {
  return useQuery({
    queryKey: ["commercial", "invoices", params ?? {}],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params?.status && params.status !== "all") query.set("status", params.status);
      if (params?.search?.trim()) query.set("search", params.search.trim());
      const qs = query.toString();
      const path = qs ? `${endpoints.commercial.invoices}?${qs}` : endpoints.commercial.invoices;
      return apiFetch<CommercialInvoice[]>(path);
    },
  });
}

export function useCommercialInvoice(invoiceId: string | null) {
  return useQuery({
    queryKey: ["commercial", "invoice", invoiceId],
    queryFn: () => apiFetch<CommercialInvoice>(endpoints.commercial.invoiceDetail(invoiceId as string)),
    enabled: Boolean(invoiceId),
  });
}

export function useCommercialInvoiceStats() {
  return useQuery({
    queryKey: ["commercial", "invoices", "stats"],
    queryFn: () => apiFetch<CommercialInvoiceStats>(endpoints.commercial.invoiceStats),
  });
}
