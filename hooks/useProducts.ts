"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { Product, ProductCreate, ProductUpdate } from "@/lib/api/types";

export function useProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: () => apiFetch<Product[]>(endpoints.products.list),
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductCreate) => apiFetch<Product>(endpoints.products.list, { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProductUpdate }) =>
      apiFetch<Product>(endpoints.products.update(id), { method: "PATCH", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<Product>(endpoints.products.delete(id), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}
