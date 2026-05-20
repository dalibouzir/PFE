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
  CommercialOrdersListResponse,
  CommercialOrder,
  CommercialOrderIntake,
  CommercialOrderStats,
  CommercialOrderStatus,
  CommercialOrderStatusUpdate,
} from "@/lib/api/types";

type CommercialOrdersQueryParams = {
  status?: CommercialOrderStatus | "all";
  search?: string;
  category?: string;
  product?: string;
  product_id?: string;
  date_from?: string;
  date_to?: string;
  client?: string;
  sort_by?: "date" | "total" | "client" | "status";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

function buildCommercialOrdersPath(params?: CommercialOrdersQueryParams) {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  if (params?.category?.trim()) query.set("category", params.category.trim());
  if (params?.product?.trim()) query.set("product", params.product.trim());
  if (params?.product_id && params.product_id !== "all") query.set("product_id", params.product_id);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.client?.trim()) query.set("client", params.client.trim());
  if (params?.sort_by) query.set("sort_by", params.sort_by);
  if (params?.sort_order) query.set("sort_order", params.sort_order);
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  const qs = query.toString();
  return qs ? `${endpoints.commercial.orders}?${qs}` : endpoints.commercial.orders;
}

async function fetchCommercialOrdersPage(params?: CommercialOrdersQueryParams): Promise<CommercialOrdersListResponse> {
  const response = await apiFetch<CommercialOrdersListResponse | CommercialOrder[]>(buildCommercialOrdersPath(params));
  if (Array.isArray(response)) {
    return {
      items: response,
      page: 1,
      page_size: response.length || 1,
      total: response.length,
      total_pages: 1,
    };
  }
  return response;
}

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

export function useCommercialOrders(params?: {
  status?: CommercialOrderStatus | "all";
  search?: string;
  category?: string;
  product?: string;
  product_id?: string;
  date_from?: string;
  date_to?: string;
  client?: string;
  sort_by?: "date" | "total" | "client" | "status";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ["commercial", "orders", params ?? {}],
    queryFn: () => fetchCommercialOrdersPage(params),
  });
}

export async function fetchCommercialOrdersForExport(params?: Omit<CommercialOrdersQueryParams, "page" | "page_size">) {
  const first = await fetchCommercialOrdersPage({ ...params, page: 1, page_size: 200 });
  const rows = [...first.items];
  for (let page = 2; page <= first.total_pages; page += 1) {
    const chunk = await fetchCommercialOrdersPage({ ...params, page, page_size: 200 });
    rows.push(...chunk.items);
  }
  return rows;
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
