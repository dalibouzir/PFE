"use client";

import { useMemo, useState } from "react";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { PageIntro } from "@/components/ui/PageIntro";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import {
  useCatalogProducts,
  useCommercialOrderStats,
  useCommercialOrders,
  useCreateCatalogProduct,
  useDeleteCatalogProduct,
  useSetCatalogProductStatus,
  useUpdateCatalogProduct,
  useUpdateCommercialOrderStatus,
} from "@/hooks/useCommercial";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import type { CatalogProduct, CommercialOrder, CommercialOrderStatus } from "@/lib/api/types";

const ORDER_STATUS_LABEL: Record<CommercialOrderStatus, string> = {
  received: "Reçue",
  confirmed: "Confirmée",
  preparing: "En préparation",
  ready: "Prête",
  delivered: "Livrée",
  paid: "Payée",
  refused: "Refusée",
};

const NEXT_ACTIONS: Partial<Record<CommercialOrderStatus, Array<{ label: string; status: CommercialOrderStatus; tone?: "default" | "danger" }>>> = {
  received: [
    { label: "Confirmer", status: "confirmed" },
    { label: "Refuser", status: "refused", tone: "danger" },
  ],
  confirmed: [
    { label: "En préparation", status: "preparing" },
    { label: "Refuser", status: "refused", tone: "danger" },
  ],
  preparing: [
    { label: "Prête", status: "ready" },
    { label: "Refuser", status: "refused", tone: "danger" },
  ],
  ready: [
    { label: "Livrée", status: "delivered" },
    { label: "Refuser", status: "refused", tone: "danger" },
  ],
  delivered: [{ label: "Payée", status: "paid" }],
};

const statusFilters: Array<{ value: "all" | CommercialOrderStatus; label: string }> = [
  { value: "all", label: "Toutes" },
  { value: "received", label: "📥 Reçue" },
  { value: "confirmed", label: "✅ Confirmée" },
  { value: "preparing", label: "⚙️ En préparation" },
  { value: "ready", label: "📦 Prête" },
  { value: "delivered", label: "🏠 Livrée" },
  { value: "paid", label: "💰 Payée" },
];

function money(value: number) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value);
}

function shortDate(value: string) {
  try {
    return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

function statusClass(status: CommercialOrderStatus) {
  switch (status) {
    case "received":
      return "bg-[#E9EEF6] text-[#37567A]";
    case "confirmed":
      return "bg-[#EAF8EE] text-[#107a3f]";
    case "preparing":
      return "bg-[#FFF4E2] text-[#C96D00]";
    case "ready":
      return "bg-[#E9F0FF] text-[#2359C2]";
    case "delivered":
      return "bg-[#E6F5F3] text-[#0f6d63]";
    case "paid":
      return "bg-[#FFF8E2] text-[#B08700]";
    case "refused":
      return "bg-[#FFEDEE] text-[#b73737]";
    default:
      return "bg-[var(--surface-soft)] text-[var(--text)]";
  }
}

export default function CommercialisationPage() {
  type CatalogFormState = {
    source_product_id: string;
    name: string;
    category: string;
    sale_unit: "kg" | "ton";
    sale_price_fcfa: string;
    cost_price_fcfa: string;
    min_order_qty: string;
    allocated_quantity: string;
    description: string;
  };

  const [tab, setTab] = useState<"catalog" | "orders" | "stats">("catalog");
  const [catalogViewMode, setCatalogViewMode] = useState<DataViewMode>("table");
  const [statusFilter, setStatusFilter] = useState<"all" | CommercialOrderStatus>("all");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [pendingPaidOrder, setPendingPaidOrder] = useState<CommercialOrder | null>(null);
  const [pendingDeleteCatalog, setPendingDeleteCatalog] = useState<CatalogProduct | null>(null);
  const [editingProduct, setEditingProduct] = useState<CatalogProduct | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [formState, setFormState] = useState<CatalogFormState>({
    source_product_id: "",
    name: "",
    category: "Fruits",
    sale_unit: "kg",
    sale_price_fcfa: "",
    cost_price_fcfa: "",
    min_order_qty: "1",
    allocated_quantity: "",
    description: "",
  });

  const { data: products = [] } = useProducts();
  const { data: stocks = [] } = useStocks();
  const { data: catalog = [] } = useCatalogProducts();
  const { data: orders = [] } = useCommercialOrders({ status: statusFilter });
  const { data: stats } = useCommercialOrderStats();
  const createCatalogProduct = useCreateCatalogProduct();
  const updateCatalogProduct = useUpdateCatalogProduct();
  const deleteCatalogProduct = useDeleteCatalogProduct();
  const setCatalogProductStatus = useSetCatalogProductStatus();
  const updateOrderStatus = useUpdateCommercialOrderStatus();
  const orderTableControls = useTableControls([], "desc");

  const visibleCatalog = useMemo(() => {
    return catalog.slice().sort((a, b) => a.name.localeCompare(b.name, "fr"));
  }, [catalog]);

  const availableSourceProducts = useMemo(() => {
    const productsById = new Map(products.map((product) => [product.id, product]));
    return stocks
      .filter((stock) => stock.total_stock_kg > 0 && stock.available_stock_kg > 0 && stock.available_stock > 0)
      .map((stock) => {
        const product = productsById.get(stock.product_id);
        if (!product) return null;
        return {
          product,
          stock,
        };
      })
      .filter((item): item is { product: (typeof products)[number]; stock: (typeof stocks)[number] } => item !== null)
      .sort((a, b) => a.product.name.localeCompare(b.product.name, "fr"));
  }, [products, stocks]);

  const selectedSourceStock = useMemo(() => {
    if (!formState.source_product_id) return null;
    return availableSourceProducts.find((item) => item.product.id === formState.source_product_id)?.stock ?? null;
  }, [availableSourceProducts, formState.source_product_id]);

  const lowStockCount = catalog.filter((item) => item.low_stock).length;
  const commandToHandle = (stats?.received ?? 0) + (stats?.confirmed ?? 0);
  const visibleOrders = useMemo(() => {
    const q = orderTableControls.search.trim().toLowerCase();
    const searched = orders.filter((order) => {
      if (!q) return true;
      const lines = order.lines.map((line) => `${line.product_name} ${line.quantity} ${line.unit}`.toLowerCase()).join(" ");
      return (
        order.order_number.toLowerCase().includes(q) ||
        order.customer_name.toLowerCase().includes(q) ||
        (order.customer_phone ?? "").toLowerCase().includes(q) ||
        lines.includes(q)
      );
    });
    const sorted = searched.slice().sort((a, b) => a.created_at.localeCompare(b.created_at));
    return orderTableControls.sortOrder === "asc" ? sorted : sorted.reverse();
  }, [orderTableControls.search, orderTableControls.sortOrder, orders]);

  function openCreateModal() {
    setEditingProduct(null);
      setFormError(null);
      setFormState({
      source_product_id: availableSourceProducts[0]?.product.id ?? "",
      name: "",
      category: "Fruits",
      sale_unit: "kg",
      sale_price_fcfa: "",
      cost_price_fcfa: "",
      min_order_qty: "1",
      allocated_quantity: "",
      description: "",
      });
    setIsFormOpen(true);
  }

  function openEditModal(item: CatalogProduct) {
    setEditingProduct(item);
    setFormError(null);
    setFormState({
      source_product_id: item.source_product_id ?? "",
      name: item.name,
      category: item.category,
      sale_unit: item.sale_unit,
      sale_price_fcfa: String(item.sale_price_fcfa),
      cost_price_fcfa: String(item.cost_price_fcfa),
      min_order_qty: String(item.min_order_qty),
      allocated_quantity: String(item.total_stock),
      description: item.description ?? "",
    });
    setIsFormOpen(true);
  }

  async function submitCatalogForm(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    try {
      const payload = {
        source_product_id: formState.source_product_id,
        name: formState.name.trim(),
        category: formState.category.trim(),
        sale_unit: formState.sale_unit,
        sale_price_fcfa: Number(formState.sale_price_fcfa),
        cost_price_fcfa: Number(formState.cost_price_fcfa),
        min_order_qty: Number(formState.min_order_qty),
        allocated_quantity: Number(formState.allocated_quantity),
        description: formState.description.trim() || null,
      };

      const selectedSource = availableSourceProducts.find((item) => item.product.id === payload.source_product_id);
      if (!selectedSource) {
        setFormError("Aucun produit disponible en stock.");
        return;
      }
      if (!Number.isFinite(payload.allocated_quantity) || payload.allocated_quantity <= 0) {
        setFormError("Quantité allouée invalide.");
        return;
      }
      if (payload.allocated_quantity > selectedSource.stock.available_stock) {
        setFormError("Quantité supérieure au stock disponible.");
        return;
      }

      if (editingProduct) {
        await updateCatalogProduct.mutateAsync({
          id: editingProduct.id,
          payload: {
            name: payload.name,
            category: payload.category,
            sale_unit: payload.sale_unit,
            sale_price_fcfa: payload.sale_price_fcfa,
            cost_price_fcfa: payload.cost_price_fcfa,
            min_order_qty: payload.min_order_qty,
            description: payload.description,
          },
        });
      } else {
        await createCatalogProduct.mutateAsync(payload);
      }

      setIsFormOpen(false);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer le produit catalogue.");
    }
  }

  async function handleToggleCatalog(item: CatalogProduct) {
    const next = item.status === "active" ? "hidden" : "active";
    await setCatalogProductStatus.mutateAsync({ id: item.id, status: next });
  }

  async function handleDeleteCatalog(item: CatalogProduct) {
    try {
      await deleteCatalogProduct.mutateAsync(item.id);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Impossible de supprimer le produit.");
    }
  }

  async function handleOrderAction(order: CommercialOrder, nextStatus: CommercialOrderStatus) {
    if (nextStatus === "paid") {
      setPendingPaidOrder(order);
      return;
    }
    await updateOrderStatus.mutateAsync({
      id: order.id,
      payload: {
        status: nextStatus,
        refused_reason: nextStatus === "refused" ? "Refusee par le manager" : undefined,
      },
    });
  }

  async function confirmMarkPaid() {
    if (!pendingPaidOrder) return;
    await updateOrderStatus.mutateAsync({
      id: pendingPaidOrder.id,
      payload: { status: "paid" },
    });
    setPendingPaidOrder(null);
  }

  const orderExportColumns: ExportColumn<CommercialOrder>[] = [
    { key: "order_number", header: "Commande" },
    { key: "created_at", header: "Date", format: (_, row) => shortDate(row.created_at) },
    { key: "customer_name", header: "Client" },
    { key: "products", header: "Produits", format: (_, row) => row.lines.map((line) => `${line.quantity} ${line.unit} ${line.product_name}`).join(" | ") },
    { key: "total_amount_fcfa", header: "Total (FCFA)", format: (_, row) => row.total_amount_fcfa.toLocaleString("fr-FR") },
    { key: "payment_method", header: "Paiement", format: (_, row) => row.payment_method ?? "-" },
    { key: "status", header: "Statut", format: (_, row) => ORDER_STATUS_LABEL[row.status] },
  ];

  return (
    <main>
      <PageIntro title="Commercialisation" />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full bg-[#FFEDEE] px-3 py-1.5 text-sm font-semibold text-[var(--danger)]">⚠️ {lowStockCount} stock(s) bas</span>
          <span className="rounded-full bg-[#FFF6E8] px-3 py-1.5 text-sm font-semibold text-[#A66E00]">🔔 {commandToHandle} commande(s) à traiter</span>
        </div>
      </section>

      <section className="mb-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => setTab("catalog")} className={`soft-focus rounded-xl border px-4 py-2 font-semibold ${tab === "catalog" ? "border-[var(--primary)] bg-[var(--primary)] text-white" : "border-[var(--line)] bg-[var(--surface)] text-[var(--text)]"}`}>
          📦 Catalogue produits
        </button>
        <button type="button" onClick={() => setTab("orders")} className={`soft-focus rounded-xl border px-4 py-2 font-semibold ${tab === "orders" ? "border-[var(--primary)] bg-[var(--primary)] text-white" : "border-[var(--line)] bg-[var(--surface)] text-[var(--text)]"}`}>
          🛒 Commandes ({stats?.total ?? 0})
        </button>
        <button type="button" onClick={() => setTab("stats")} className={`soft-focus rounded-xl border px-4 py-2 font-semibold ${tab === "stats" ? "border-[var(--primary)] bg-[var(--primary)] text-white" : "border-[var(--line)] bg-[var(--surface)] text-[var(--text)]"}`}>
          📊 Statistiques
        </button>
      </section>

      {tab === "catalog" && (
        <>
          <section className="mb-4 flex items-center justify-between gap-3">
            <button type="button" onClick={openCreateModal} className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]">
              + Nouveau produit catalogue
            </button>
            <div className="flex items-center gap-3">
              <p className="text-xs text-[var(--muted)]">Ces produits sont visibles dans l&apos;app consommateur.</p>
              <GlassViewToggle value={catalogViewMode} onChange={setCatalogViewMode} className="shrink-0" />
            </div>
          </section>

          {catalogViewMode === "cards" ? (
            <>
              {visibleCatalog.length === 0 ? (
                <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "40ms" }}>
                  <p className="text-sm text-[var(--muted)]">Aucun produit catalogue pour le moment.</p>
                </section>
              ) : (
                <section className="grid gap-4 xl:grid-cols-3">
                  {visibleCatalog.map((item, index) => (
                    <article key={item.id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${45 + index * 20}ms` }}>
                      <div className="flex items-start justify-between gap-2">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${item.status === "active" ? "bg-[#EAF8EE] text-[#0F7A3B]" : "bg-[#FFEDEE] text-[#A83C3C]"}`}>
                          {item.status === "active" ? "● En stock" : "○ Hors stock / masqué"}
                        </span>
                        <span className="text-sm font-semibold text-[var(--muted)]">{item.category}</span>
                      </div>

                      <h3 className="mt-3 text-xl font-semibold text-[var(--text)]">{item.name}</h3>
                      <p className="mt-1 line-clamp-2 text-sm text-[var(--muted)]">{item.description || "Aucune description"}</p>

                      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2.5">
                          <p className="text-xs text-[var(--muted)]">Prix vente</p>
                          <p className="font-semibold text-[var(--success)]">{money(item.sale_price_fcfa)} FCFA / {item.sale_unit}</p>
                        </div>
                        <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2.5">
                          <p className="text-xs text-[var(--muted)]">Disponibles</p>
                          <p className="font-semibold text-[var(--text)]">{item.available_stock.toFixed(2)} {item.sale_unit}</p>
                        </div>
                      </div>

                      <div className="mt-3 flex items-center justify-between text-xs">
                        <span className="text-[var(--muted)]">Min commande: {item.min_order_qty} {item.sale_unit}</span>
                        <span className="rounded-full bg-[#EAF8EE] px-2 py-1 font-semibold text-[#0F7A3B]">Marge {item.margin_percent}%</span>
                      </div>

                      {item.low_stock && <p className="mt-2 text-xs font-semibold text-[var(--danger)]">Stock bas: pensez à masquer ce produit.</p>}

                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => openEditModal(item)} className="soft-focus rounded-xl border border-[#A7C3F0] px-3 py-2 text-sm font-semibold text-[#1F5EA8] hover:bg-[#EEF5FF]">
                          Modifier
                        </button>
                        <button type="button" onClick={() => handleToggleCatalog(item)} className={`soft-focus rounded-xl border px-3 py-2 text-sm font-semibold ${item.status === "active" ? "border-[#E0A5A5] text-[#A83C3C] hover:bg-[#FFF0F0]" : "border-[#9DD3AF] text-[#0F7A3B] hover:bg-[#EFFAF2]"}`}>
                          {item.status === "active" ? "Masquer" : "Activer"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPendingDeleteCatalog(item)}
                          disabled={deleteCatalogProduct.isPending}
                          className="soft-focus col-span-2 rounded-xl border border-[#E0A5A5] px-3 py-2 text-sm font-semibold text-[#A83C3C] hover:bg-[#FFF0F0] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Supprimer
                        </button>
                      </div>
                    </article>
                  ))}
                </section>
              )}
            </>
          ) : (
            <section className="premium-card overflow-hidden rounded-2xl">
              <div className="overflow-x-auto">
                <table className="wf-table min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left">Produit</th>
                      <th className="px-4 py-3 text-left">Catégorie</th>
                      <th className="px-4 py-3 text-left">Statut</th>
                      <th className="px-4 py-3 text-left">Disponibles</th>
                      <th className="px-4 py-3 text-left">Total</th>
                      <th className="px-4 py-3 text-left">Prix vente</th>
                      <th className="px-4 py-3 text-left">Marge</th>
                      <th className="px-4 py-3 text-left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCatalog.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-5 text-center text-sm text-[var(--muted)]">
                          Aucun produit catalogue pour le moment.
                        </td>
                      </tr>
                    ) : (
                      visibleCatalog.map((item) => (
                        <tr key={item.id}>
                          <td className="px-4 py-3 font-semibold text-[var(--text)]">{item.name}</td>
                          <td className="px-4 py-3 text-[var(--muted)]">{item.category}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${item.status === "active" ? "bg-[#EAF8EE] text-[#0F7A3B]" : "bg-[#FFEDEE] text-[#A83C3C]"}`}>
                              {item.status === "active" ? "En stock" : "Masqué"}
                            </span>
                          </td>
                          <td className="px-4 py-3">{item.available_stock.toFixed(2)} {item.sale_unit}</td>
                          <td className="px-4 py-3">{item.total_stock.toFixed(2)} {item.sale_unit}</td>
                          <td className="px-4 py-3 font-semibold text-[var(--success)]">{money(item.sale_price_fcfa)} FCFA</td>
                          <td className="px-4 py-3 font-semibold text-[#0F7A3B]">{item.margin_percent}%</td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-2">
                              <button type="button" onClick={() => openEditModal(item)} className="soft-focus rounded-xl border border-[#A7C3F0] px-3 py-1.5 text-sm font-semibold text-[#1F5EA8] hover:bg-[#EEF5FF]">
                                Modifier
                              </button>
                              <button type="button" onClick={() => handleToggleCatalog(item)} className={`soft-focus rounded-xl border px-3 py-1.5 text-sm font-semibold ${item.status === "active" ? "border-[#E0A5A5] text-[#A83C3C] hover:bg-[#FFF0F0]" : "border-[#9DD3AF] text-[#0F7A3B] hover:bg-[#EFFAF2]"}`}>
                                {item.status === "active" ? "Masquer" : "Activer"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setPendingDeleteCatalog(item)}
                                disabled={deleteCatalogProduct.isPending}
                                className="soft-focus rounded-xl border border-[#E0A5A5] px-3 py-1.5 text-sm font-semibold text-[#A83C3C] hover:bg-[#FFF0F0] disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                Supprimer
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}

      {tab === "orders" && (
        <>
          <section className="mb-4 flex flex-wrap gap-2">
            {statusFilters.map((filter) => {
              const count =
                filter.value === "all"
                  ? stats?.total ?? 0
                  : stats?.[filter.value as keyof typeof stats] ?? 0;
              const active = statusFilter === filter.value;
              return (
                <button
                  key={filter.value}
                  type="button"
                  onClick={() => setStatusFilter(filter.value)}
                  className={`soft-focus rounded-xl border px-3 py-2 text-sm font-semibold ${active ? "border-[var(--primary)] bg-[var(--primary)] text-white" : "border-[var(--line)] bg-[var(--surface)] text-[var(--text)]"}`}
                >
                  {filter.label} ({count as number})
                </button>
              );
            })}
          </section>

          <section className="grid gap-3 md:grid-cols-4">
            <article className="premium-card rounded-2xl p-4">
              <p className="text-xs text-[var(--muted)]">Nouvelles</p>
              <p className="mt-1 text-4xl font-semibold text-[var(--text)]">{stats?.new_count ?? 0}</p>
            </article>
            <article className="premium-card rounded-2xl p-4">
              <p className="text-xs text-[var(--muted)]">En cours</p>
              <p className="mt-1 text-4xl font-semibold text-[var(--text)]">{stats?.in_progress_count ?? 0}</p>
            </article>
            <article className="premium-card rounded-2xl p-4">
              <p className="text-xs text-[var(--muted)]">Payées ce mois</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--success)]">{money(stats?.paid_this_month_fcfa ?? 0)} FCFA</p>
            </article>
            <article className="premium-card rounded-2xl p-4">
              <p className="text-xs text-[var(--muted)]">Refusées</p>
              <p className="mt-1 text-4xl font-semibold text-[var(--danger)]">{stats?.refused ?? 0}</p>
            </article>
          </section>

          <section className="premium-card mt-4 overflow-hidden rounded-2xl">
            <div className="border-b border-[var(--line)] p-4">
              <TableToolbar
                search={orderTableControls.search}
                onSearchChange={orderTableControls.setSearch}
                searchPlaceholder="Recherche commande, client, téléphone, produit..."
                sortOrder={orderTableControls.sortOrder}
                onSortOrderChange={orderTableControls.setSortOrder}
                sortAscLabel="Date asc"
                sortDescLabel="Date desc"
                rightActions={
                  <ExportActions
                    onCsv={() => exportRowsToCsv({ filename: "commandes", title: "Commandes", columns: orderExportColumns, rows: visibleOrders })}
                    onExcel={() => exportRowsToExcel({ filename: "commandes", title: "Commandes", columns: orderExportColumns, rows: visibleOrders })}
                    onPdf={() => exportRowsToPdf({ filename: "commandes", title: "Commandes", columns: orderExportColumns, rows: visibleOrders })}
                  />
                }
              />
            </div>
            <div className="overflow-x-auto">
              <table className="wf-table min-w-full text-sm">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left">N°</th>
                    <th className="px-4 py-3 text-left">Date</th>
                    <th className="px-4 py-3 text-left">Client</th>
                    <th className="px-4 py-3 text-left">Produits</th>
                    <th className="px-4 py-3 text-left">Total</th>
                    <th className="px-4 py-3 text-left">Paiement</th>
                    <th className="px-4 py-3 text-left">Statut</th>
                    <th className="px-4 py-3 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleOrders.map((order) => (
                    <tr key={order.id}>
                      <td className="px-4 py-3 font-semibold text-[var(--primary)]">{order.order_number}</td>
                      <td className="px-4 py-3 text-[var(--muted)]">{shortDate(order.created_at)}</td>
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[var(--text)]">{order.customer_name}</p>
                        <p className="text-xs text-[var(--muted)]">{order.customer_phone ?? "-"}</p>
                      </td>
                      <td className="px-4 py-3">
                        {order.lines.map((line) => (
                          <p key={line.id} className="text-[var(--text)]">
                            {line.quantity} {line.unit} {line.product_name}
                          </p>
                        ))}
                      </td>
                      <td className="px-4 py-3 text-lg font-semibold text-[var(--success)]">{money(order.total_amount_fcfa)} FCFA</td>
                      <td className="px-4 py-3 text-[var(--text)]">{order.payment_method ?? "-"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-sm font-semibold ${statusClass(order.status)}`}>
                          {ORDER_STATUS_LABEL[order.status]}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {(NEXT_ACTIONS[order.status] || []).map((action) => (
                            <button
                              key={action.status}
                              type="button"
                              onClick={() => handleOrderAction(order, action.status)}
                              className={`soft-focus rounded-xl border px-3 py-1.5 text-sm font-semibold ${action.tone === "danger" ? "border-[#E0A5A5] text-[#A83C3C] hover:bg-[#FFF0F0]" : "border-[#B5D6BE] text-[#0F7A3B] hover:bg-[#EFFAF2]"}`}
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {visibleOrders.length === 0 && (
                    <tr>
                      <td className="px-4 py-5 text-center text-sm text-[var(--muted)]" colSpan={8}>
                        Aucune commande pour ce filtre.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {tab === "stats" && (
        <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <article className="premium-card rounded-2xl p-5">
            <h3 className="text-lg font-semibold text-[var(--text)]">Revenus potentiels par produit</h3>
            <div className="mt-4 space-y-3">
              {catalog
                .slice()
                .sort((a, b) => b.sale_price_fcfa - a.sale_price_fcfa)
                .slice(0, 6)
                .map((item) => (
                  <div key={item.id}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-semibold text-[var(--text)]">{item.name}</span>
                      <span className="text-[var(--muted)]">{money(item.sale_price_fcfa)} FCFA</span>
                    </div>
                    <div className="h-2 rounded-full bg-[#ECE7DF]">
                      <div className="h-2 rounded-full bg-[var(--primary)]" style={{ width: `${Math.min(100, (item.sale_price_fcfa / Math.max(...catalog.map((c) => c.sale_price_fcfa), 1)) * 100)}%` }} />
                    </div>
                  </div>
                ))}
            </div>
          </article>

          <article className="premium-card rounded-2xl p-5">
            <h3 className="text-lg font-semibold text-[var(--text)]">Statuts des commandes</h3>
            <div className="mt-4 space-y-2 text-sm">
              {([
                ["Reçue", stats?.received ?? 0],
                ["Confirmée", stats?.confirmed ?? 0],
                ["En préparation", stats?.preparing ?? 0],
                ["Prête", stats?.ready ?? 0],
                ["Livrée", stats?.delivered ?? 0],
                ["Payée", stats?.paid ?? 0],
                ["Refusée", stats?.refused ?? 0],
              ] as const).map(([label, count]) => (
                <div key={label} className="flex items-center justify-between rounded-xl bg-[var(--surface-soft)] px-3 py-2">
                  <span className="text-[var(--text)]">{label}</span>
                  <span className="font-semibold text-[var(--text)]">{count}</span>
                </div>
              ))}
            </div>
          </article>
        </section>
      )}

      {isFormOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4">
          <div className="w-full max-w-3xl rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-[var(--text)]">{editingProduct ? "Modifier produit catalogue" : "Nouveau produit catalogue"}</h3>
              <button type="button" onClick={() => setIsFormOpen(false)} className="soft-focus rounded-lg border border-[var(--line)] px-2 py-1 text-sm text-[var(--muted)]">✕</button>
            </div>

            <form onSubmit={submitCatalogForm} className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-medium text-[var(--text)]">
                Produit source (stock)
                <select
                  value={formState.source_product_id}
                  onChange={(event) => setFormState((prev) => ({ ...prev, source_product_id: event.target.value }))}
                  disabled={Boolean(editingProduct)}
                  className="wf-input mt-1 h-11 w-full px-3"
                  required
                >
                  <option value="">Selectionner</option>
                  {availableSourceProducts.map(({ product, stock }) => (
                    <option key={product.id} value={product.id}>
                      {product.name} — {stock.available_stock.toFixed(2)} {stock.unit} disponible
                    </option>
                  ))}
                </select>
                {availableSourceProducts.length === 0 ? (
                  <p className="mt-1 text-xs text-[var(--muted)]">Aucun produit disponible en stock.</p>
                ) : null}
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Nom produit catalogue
                <input value={formState.name} onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))} className="wf-input mt-1 h-11 w-full px-3" required />
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Categorie
                <input value={formState.category} onChange={(event) => setFormState((prev) => ({ ...prev, category: event.target.value }))} className="wf-input mt-1 h-11 w-full px-3" required />
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Unite de vente
                <select value={formState.sale_unit} onChange={(event) => setFormState((prev) => ({ ...prev, sale_unit: event.target.value as "kg" | "ton" }))} className="wf-input mt-1 h-11 w-full px-3" required>
                  <option value="kg">kg</option>
                  <option value="ton">ton</option>
                </select>
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Prix vente (FCFA)
                <input type="number" min="1" step="0.01" value={formState.sale_price_fcfa} onChange={(event) => setFormState((prev) => ({ ...prev, sale_price_fcfa: event.target.value }))} className="wf-input mt-1 h-11 w-full px-3" required />
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Prix de revient (FCFA)
                <input type="number" min="0" step="0.01" value={formState.cost_price_fcfa} onChange={(event) => setFormState((prev) => ({ ...prev, cost_price_fcfa: event.target.value }))} className="wf-input mt-1 h-11 w-full px-3" required />
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Minimum commande
                <input type="number" min="0.01" step="0.01" value={formState.min_order_qty} onChange={(event) => setFormState((prev) => ({ ...prev, min_order_qty: event.target.value }))} className="wf-input mt-1 h-11 w-full px-3" required />
              </label>

              <label className="text-sm font-medium text-[var(--text)]">
                Quantite allouee depuis stock principal
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  max={selectedSourceStock?.available_stock ?? undefined}
                  value={formState.allocated_quantity}
                  onChange={(event) => setFormState((prev) => ({ ...prev, allocated_quantity: event.target.value }))}
                  className="wf-input mt-1 h-11 w-full px-3"
                  required
                  disabled={Boolean(editingProduct)}
                />
                {!editingProduct && selectedSourceStock ? (
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Disponible: {selectedSourceStock.available_stock.toFixed(2)} {selectedSourceStock.unit}
                  </p>
                ) : null}
              </label>

              <label className="text-sm font-medium text-[var(--text)] md:col-span-2">
                Description consommateur
                <textarea value={formState.description} onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))} className="wf-input mt-1 min-h-[90px] w-full px-3 py-2" />
              </label>

              {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f] md:col-span-2">{formError}</p>}

              <div className="flex justify-end gap-2 md:col-span-2">
                <button type="button" onClick={() => setIsFormOpen(false)} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--text)]">
                  Annuler
                </button>
                <button type="submit" className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]" disabled={createCatalogProduct.isPending || updateCatalogProduct.isPending}>
                  {editingProduct ? "Enregistrer" : "Publier dans le catalogue"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <ConfirmActionModal
        open={Boolean(pendingPaidOrder)}
        title="Marquer la commande comme Payée"
        message="Cette action confirme le paiement et déclenche la facture/revenu de trésorerie de façon idempotente."
        confirmLabel="Oui, marquer Payée"
        loading={updateOrderStatus.isPending}
        onCancel={() => setPendingPaidOrder(null)}
        onConfirm={() => {
          void confirmMarkPaid();
        }}
      />
      <ConfirmActionModal
        open={Boolean(pendingDeleteCatalog)}
        title="Supprimer le produit catalogue"
        message={pendingDeleteCatalog ? `Supprimer "${pendingDeleteCatalog.name}" du catalogue ?` : "Supprimer ce produit du catalogue ?"}
        confirmLabel="Supprimer"
        loading={deleteCatalogProduct.isPending}
        onCancel={() => setPendingDeleteCatalog(null)}
        onConfirm={() => {
          if (!pendingDeleteCatalog) return;
          void handleDeleteCatalog(pendingDeleteCatalog);
          setPendingDeleteCatalog(null);
        }}
      />
    </main>
  );
}
