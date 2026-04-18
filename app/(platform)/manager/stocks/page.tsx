"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { TrendingDown, TrendingUp } from "lucide-react";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useBatches } from "@/hooks/useBatches";
import { useInputs } from "@/hooks/useInputs";
import { useProcessSteps } from "@/hooks/useProcessSteps";
import { useAdjustStock, useCreateStock, useDeleteStock, useStocks, useUpdateStock } from "@/hooks/useStocks";
import { useProducts } from "@/hooks/useProducts";
import type { Stock, StockCreate, StockUpdate } from "@/lib/api/types";

const statusTone: Record<string, "success" | "warning" | "danger"> = {
  ok: "success",
  warning: "warning",
  critical: "danger",
};

function isCurrentMonth(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
}

export default function StocksPage() {
  const { data: stocks = [] } = useStocks();
  const { data: products = [] } = useProducts();
  const { data: inputs = [] } = useInputs();
  const { data: steps = [] } = useProcessSteps();
  const { data: batches = [] } = useBatches();
  const createStock = useCreateStock();
  const updateStock = useUpdateStock();
  const deleteStock = useDeleteStock();
  const adjustStock = useAdjustStock();
  const [productId, setProductId] = useState<string>("Tous");
  const [formOpen, setFormOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [editingStock, setEditingStock] = useState<Stock | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState } = useForm<StockCreate>({
    defaultValues: { product_id: "", quantity: 0, threshold: 0, unit: "kg" },
  });

  const adjustForm = useForm<{ amount: number; direction: "increase" | "decrease" }>({
    defaultValues: { amount: 0, direction: "increase" },
  });

  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);

  const filtered = useMemo(() => {
    return stocks.filter((item) => (productId === "Tous" ? true : item.product_id === productId));
  }, [stocks, productId]);

  const batchProductLookup = useMemo(() => {
    return new Map(batches.map((item) => [item.id, item.product_id]));
  }, [batches]);

  const entriesByProduct = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of inputs) {
      if (!isCurrentMonth(item.date)) continue;
      map.set(item.product_id, (map.get(item.product_id) ?? 0) + item.quantity);
    }
    return map;
  }, [inputs]);

  const sortiesByProduct = useMemo(() => {
    const map = new Map<string, number>();
    for (const step of steps) {
      if (!isCurrentMonth(step.date)) continue;
      const product = batchProductLookup.get(step.batch_id);
      if (!product) continue;
      map.set(product, (map.get(product) ?? 0) + step.qty_out);
    }
    return map;
  }, [steps, batchProductLookup]);

  const criticalCount = filtered.filter((item) => item.quantity < item.threshold).length;
  const stockCards = useMemo(() => {
    const grouped = new Map<
      string,
      {
        product_id: string;
        quantity: number;
        threshold: number;
        unit: string;
      }
    >();

    for (const item of filtered) {
      const current = grouped.get(item.product_id);
      if (!current) {
        grouped.set(item.product_id, {
          product_id: item.product_id,
          quantity: item.quantity,
          threshold: item.threshold,
          unit: item.unit,
        });
      } else {
        current.quantity += item.quantity;
        current.threshold += item.threshold;
      }
    }

    return Array.from(grouped.values())
      .sort((a, b) => b.threshold - b.quantity - (a.threshold - a.quantity))
      .slice(0, 6);
  }, [filtered]);

  const openCreateForm = () => {
    setEditingStock(null);
    reset({ product_id: products[0]?.id ?? "", quantity: 0, threshold: 0, unit: "kg" });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (stock: Stock) => {
    setEditingStock(stock);
    reset({ product_id: stock.product_id, quantity: stock.quantity, threshold: stock.threshold, unit: stock.unit });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const openAdjustForm = (stock: Stock) => {
    setEditingStock(stock);
    adjustForm.reset({ amount: 0, direction: "increase" });
    setFormError(null);
    setAdjustOpen(true);
  };

  const closeAdjustForm = () => {
    setAdjustOpen(false);
    setFormError(null);
  };

  const submitStock = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: StockCreate = {
        product_id: values.product_id,
        quantity: Number(values.quantity),
        threshold: Number(values.threshold),
        unit: values.unit.trim(),
      };

      if (editingStock) {
        const updatePayload: StockUpdate = {
          threshold: payload.threshold,
          unit: payload.unit,
        };
        await updateStock.mutateAsync({ id: editingStock.id, payload: updatePayload });
      } else {
        await createStock.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer le stock.");
    }
  });

  const submitAdjustment = adjustForm.handleSubmit(async (values) => {
    if (!editingStock) return;
    setFormError(null);
    try {
      await adjustStock.mutateAsync({
        id: editingStock.id,
        direction: values.direction,
        payload: { amount: Number(values.amount) },
      });
      closeAdjustForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'ajuster le stock.");
    }
  });

  const handleDeleteStock = async (stock: Stock) => {
    if (!window.confirm("Supprimer cette ligne de stock ?")) return;
    try {
      await deleteStock.mutateAsync(stock.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer le stock.");
    }
  };

  return (
    <main>
      <PageIntro title="Stocks" subtitle="Vue inventaire simplifiee: niveaux actuels, seuils critiques et actions de reapprovisionnement." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
          <select
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option value="Tous">Tous produits</option>
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <div className="rounded-xl border border-[#E8B9B9] bg-[#FFEDEE] px-3 py-2 text-sm text-[var(--danger)]">
            Alertes critiques: <span className="font-semibold">{criticalCount}</span>
          </div>
          <button
            type="button"
            onClick={openCreateForm}
            className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold"
          >
            Nouveau stock
          </button>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {stockCards.length === 0 ? (
          <article className="premium-card reveal rounded-2xl p-5 sm:col-span-2 xl:col-span-3" style={{ ["--delay" as string]: "70ms" }}>
            <p className="text-sm text-[var(--muted)]">Aucun produit de stock a afficher pour ce filtre.</p>
          </article>
        ) : (
          stockCards.map((item, index) => {
            const isCritical = item.quantity < item.threshold;
            const delta = item.quantity - item.threshold;
            const entries = entriesByProduct.get(item.product_id) ?? 0;
            const sorties = sortiesByProduct.get(item.product_id) ?? 0;
            const capacity = Math.max(item.threshold * 2, item.quantity, 1);
            const progress = Math.max(6, Math.min((item.quantity / capacity) * 100, 100));
            const barClass = isCritical
              ? "bg-gradient-to-r from-red-400 to-red-600"
              : item.quantity < item.threshold * 1.4
                ? "bg-gradient-to-r from-amber-400 to-amber-600"
                : "bg-gradient-to-r from-green-400 to-green-600";
            return (
              <article key={item.product_id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${70 + index * 25}ms` }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                    <p className="text-xs text-[var(--muted)]">Seuil {item.threshold.toFixed(1)} {item.unit}</p>
                  </div>
                  <StatusBadge label={isCritical ? "Critique" : "Stable"} tone={isCritical ? "danger" : "success"} />
                </div>
                <p className="mt-3 text-2xl font-semibold text-[var(--text)]">{item.quantity.toFixed(1)} {item.unit}</p>
                <p className={`mt-1 text-xs font-semibold ${isCritical ? "text-[var(--danger)]" : "text-[var(--success)]"}`}>
                  {isCritical ? "Sous seuil" : "Au-dessus du seuil"} · {delta >= 0 ? "+" : ""}{delta.toFixed(1)} {item.unit}
                </p>
                <div className="mt-3 h-2.5 rounded-full bg-[#E8E3DB]">
                  <div className={`h-2.5 rounded-full ${barClass}`} style={{ width: `${progress}%` }} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-[#F4FAF5] px-2 py-1.5">
                    <p className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--success)]">
                      <TrendingUp className="h-3.5 w-3.5" />
                      +{entries.toFixed(0)}
                    </p>
                    <p className="text-[11px] text-[var(--muted)]">Entrees</p>
                  </div>
                  <div className="rounded-lg bg-[#FFF6EF] px-2 py-1.5">
                    <p className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#B86A12]">
                      <TrendingDown className="h-3.5 w-3.5" />
                      -{sorties.toFixed(0)}
                    </p>
                    <p className="text-[11px] text-[var(--muted)]">Sorties</p>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal mt-4 rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun stock enregistre. Creez une premiere ligne pour demarrer le suivi.</p>
        </section>
      ) : (
        <section className="premium-card reveal mt-4 overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "120ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Quantite</th>
                  <th className="px-5 py-3.5">Seuil</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const status = item.quantity < item.threshold ? "critical" : "ok";
                  return (
                    <tr key={item.id}>
                      <td className="px-5 py-4 font-medium text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                      <td className="px-5 py-4">{item.quantity.toFixed(1)} {item.unit}</td>
                      <td className="px-5 py-4">{item.threshold.toFixed(1)} {item.unit}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={status === "critical" ? "Critique" : "Correct"} tone={statusTone[status]} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditForm(item)}>
                            Modifier
                          </button>
                          <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openAdjustForm(item)}>
                            Ajuster
                          </button>
                          <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => handleDeleteStock(item)}>
                            Supprimer
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingStock ? "Modifier stock" : "Nouveau stock"}
        subtitle="Le seuil et l'unite peuvent etre ajustes par produit."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="stock-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="stock-form" onSubmit={submitStock} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Produit
            <select
              {...register("product_id", { required: "Produit requis." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              disabled={Boolean(editingStock)}
            >
              <option value="" disabled>
                Selectionner un produit
              </option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </label>
          {!editingStock && (
            <label className="block text-sm font-medium text-[var(--text)]">
              Quantite initiale
              <input type="number" step="0.1" min="0" {...register("quantity", { required: "Quantite requise.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
          )}
          <label className="block text-sm font-medium text-[var(--text)]">
            Seuil
            <input type="number" step="0.1" min="0" {...register("threshold", { required: "Seuil requis.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Unite
            <input {...register("unit", { required: "Unite requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={adjustOpen}
        onClose={closeAdjustForm}
        title="Ajuster stock"
        subtitle={editingStock ? `Produit ${productLookup.get(editingStock.product_id) ?? editingStock.product_id.slice(0, 8)}` : undefined}
        size="sm"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeAdjustForm}>
              Annuler
            </button>
            <button type="submit" form="stock-adjust-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={adjustForm.formState.isSubmitting}>
              {adjustForm.formState.isSubmitting ? "Mise a jour..." : "Appliquer"}
            </button>
          </div>
        }
      >
        <form id="stock-adjust-form" onSubmit={submitAdjustment} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Direction
            <select {...adjustForm.register("direction")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="increase">Ajouter</option>
              <option value="decrease">Retirer</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Quantite
            <input type="number" step="0.1" min="0" {...adjustForm.register("amount", { required: "Quantite requise.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
