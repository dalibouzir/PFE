"use client";

import { useCallback, useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useBatches } from "@/hooks/useBatches";
import { useCatalogProducts, useCommercialOrders } from "@/hooks/useCommercial";
import { useInputs } from "@/hooks/useInputs";
import { useProcessSteps } from "@/hooks/useProcessSteps";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import type { Stock } from "@/lib/api/types";

type ViewMode = "cards" | "table";
type LogOrder = "newest" | "oldest";
type MovementReason = "collecte" | "commercialisation" | "perte_lot" | "sortie_lot";

type StockMovementEvent = {
  id: string;
  product_id: string;
  date: string;
  quantity_kg: number;
  delta_kg: number;
  reason: MovementReason;
  reference: string;
  note?: string | null;
};

type StockMovementWithBalances = StockMovementEvent & {
  before_kg: number;
  after_kg: number;
};

export default function StocksPage() {
  const { data: stocks = [] } = useStocks();
  const { data: products = [] } = useProducts();
  const { data: inputs = [] } = useInputs();
  const { data: batches = [] } = useBatches();
  const { data: processSteps = [] } = useProcessSteps();
  const { data: orders = [] } = useCommercialOrders();
  const { data: catalogProducts = [] } = useCatalogProducts();

  const [productId, setProductId] = useState<string>("Tous");
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [logOrder, setLogOrder] = useState<LogOrder>("newest");

  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);
  const productByNormalizedName = useMemo(() => {
    const map = new Map<string, (typeof products)[number]>();
    for (const product of products) {
      const key = normalizeToken(product.name);
      if (!map.has(key)) map.set(key, product);
    }
    return map;
  }, [products]);

  const batchById = useMemo(() => {
    return new Map(batches.map((batch) => [batch.id, batch]));
  }, [batches]);

  const currentQtyByProductKg = useMemo(() => {
    const map = new Map<string, number>();
    for (const batch of batches) {
      if (!batch.confirmed_weight_kg) continue;
      const currentKg = Math.max(batch.current_qty ?? batch.confirmed_weight_kg ?? 0, 0);
      map.set(batch.product_id, (map.get(batch.product_id) ?? 0) + currentKg);
    }
    return map;
  }, [batches]);

  const remainingKgForProduct = useCallback(
    (item: Stock) => {
      const fromLots = currentQtyByProductKg.get(item.product_id);
      if (fromLots === undefined) return item.available_stock_kg;
      return fromLots;
    },
    [currentQtyByProductKg],
  );

  const filtered = useMemo(() => {
    return stocks.filter((item) => (productId === "Tous" ? true : item.product_id === productId));
  }, [stocks, productId]);

  const filteredByUrgency = useMemo(() => {
    return filtered.slice().sort((a, b) => {
      const remainingA = remainingKgForProduct(a);
      const remainingB = remainingKgForProduct(b);
      return stockUrgencyScore(a.total_stock_kg, remainingA) - stockUrgencyScore(b.total_stock_kg, remainingB);
    });
  }, [filtered, remainingKgForProduct]);

  const criticalCount = useMemo(
    () => filtered.filter((item) => isCriticalStock(item.total_stock_kg, remainingKgForProduct(item))).length,
    [filtered, remainingKgForProduct],
  );

  const collectedByProductKg = useMemo(() => {
    const map = new Map<string, number>();
    for (const input of inputs) {
      map.set(input.product_id, (map.get(input.product_id) ?? 0) + input.quantity);
    }
    return map;
  }, [inputs]);

  const catalogById = useMemo(() => {
    return new Map(catalogProducts.map((item) => [item.id, item]));
  }, [catalogProducts]);

  const movementEvents = useMemo(() => {
    const events: StockMovementEvent[] = [];

    for (const input of inputs) {
      events.push({
        id: `collecte-${input.id}`,
        product_id: input.product_id,
        date: input.created_at || input.updated_at || `${input.date}T00:00:00Z`,
        quantity_kg: input.quantity,
        delta_kg: input.quantity,
        reason: "collecte",
        reference: `COL-${input.id.slice(0, 8).toUpperCase()}`,
      });
    }

    for (const step of processSteps) {
      const batch = batchById.get(step.batch_id);
      if (!batch) continue;
      const qtyKg = Math.max(step.normalized_loss_value ?? 0, 0);
      if (qtyKg <= 0) continue;
      const reason: MovementReason = isExitReason(step.type) ? "sortie_lot" : "perte_lot";
      events.push({
        id: `step-${step.id}`,
        product_id: batch.product_id,
        date: step.created_at || step.updated_at || `${step.date}T00:00:00Z`,
        quantity_kg: qtyKg,
        delta_kg: -qtyKg,
        reason,
        reference: batch.code,
        note: `${step.type}${step.notes ? ` · ${step.notes}` : ""}`,
      });
    }

    for (const order of orders) {
      if (order.status !== "delivered" && order.status !== "paid") continue;
      const movementDate = order.delivered_at || order.paid_at || order.updated_at || order.created_at;
      for (const line of order.lines) {
        const catalog = catalogById.get(line.catalog_product_id);
        let sourceProductId = catalog?.source_product_id ?? null;
        if (!sourceProductId) {
          const sourceName = catalog?.source_product_name || line.product_name;
          sourceProductId = productByNormalizedName.get(normalizeToken(sourceName))?.id ?? null;
        }
        if (!sourceProductId) continue;

        const qtyKg = toKg(line.quantity, line.unit);
        events.push({
          id: `commercial-${order.id}-${line.id}`,
          product_id: sourceProductId,
          date: movementDate,
          quantity_kg: qtyKg,
          delta_kg: -qtyKg,
          reason: "commercialisation",
          reference: order.order_number,
          note: order.customer_name,
        });
      }
    }

    return events;
  }, [batchById, catalogById, inputs, orders, processSteps, productByNormalizedName]);

  const stockByProduct = useMemo(() => {
    return new Map(filtered.map((item) => [item.product_id, item]));
  }, [filtered]);

  const movementRows = useMemo(() => {
    const relevant = movementEvents
      .filter((event) => stockByProduct.has(event.product_id))
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    const cursor = new Map<string, number>();
    for (const [id, stock] of stockByProduct) {
      cursor.set(id, stock.available_stock_kg);
    }

    const computed: StockMovementWithBalances[] = [];
    for (const event of relevant) {
      const after = cursor.get(event.product_id) ?? 0;
      const before = after - event.delta_kg;
      cursor.set(event.product_id, before);
      computed.push({
        ...event,
        before_kg: before,
        after_kg: after,
      });
    }

    const ordered = logOrder === "newest" ? computed : computed.slice().reverse();
    return ordered.slice(0, 120);
  }, [logOrder, movementEvents, stockByProduct]);

  return (
    <main>
      <PageIntro title="Stocks" />

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

          <select
            value={logOrder}
            onChange={(event) => setLogOrder(event.target.value as LogOrder)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option value="newest">Journal: plus récent</option>
            <option value="oldest">Journal: plus ancien</option>
          </select>

          <div className="flex items-center gap-3">
            <div className="rounded-xl border border-[#E8B9B9] bg-[#FFEDEE] px-3 py-2 text-sm text-[var(--danger)]">
              Alertes critiques: <span className="font-semibold">{criticalCount}</span>
            </div>
            <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-1">
              <button
                onClick={() => setViewMode("cards")}
                className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "cards" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
              >
                Cartes
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "table" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
              >
                Tableau
              </button>
            </div>
          </div>
        </div>
      </section>

      {viewMode === "cards" ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filteredByUrgency.length === 0 ? (
            <article className="premium-card reveal rounded-2xl p-5 sm:col-span-2 xl:col-span-3" style={{ ["--delay" as string]: "70ms" }}>
              <p className="text-sm text-[var(--muted)]">Aucun produit de stock à afficher pour ce filtre.</p>
            </article>
          ) : (
            filteredByUrgency.map((item, index) => {
              const remainingKg = remainingKgForProduct(item);
              const remainingDisplay = fromKg(remainingKg, item.unit);
              const isCritical = isCriticalStock(item.total_stock_kg, remainingKg);
              const total = item.total_stock;
              const inLot = item.reserved_in_lots;
              const remaining = remainingDisplay;
              const threshold = total * 0.2;
              const progress = total > 0 ? Math.max(6, Math.min((remaining / total) * 100, 100)) : 0;
              const barClass = isCritical
                ? "bg-gradient-to-r from-red-400 to-red-600"
                : total > 0 && remaining < threshold * 1.4
                  ? "bg-gradient-to-r from-amber-400 to-amber-600"
                  : "bg-gradient-to-r from-green-400 to-green-600";
              return (
                <article key={item.product_id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${70 + index * 25}ms` }}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                      <p className="text-xs text-[var(--muted)]">Critique si restant &lt; 20% du total</p>
                    </div>
                    <StatusBadge label={isCritical ? "Critique" : "Stable"} tone={isCritical ? "danger" : "success"} />
                  </div>

                  <p className="mt-4 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">Stock total</p>
                  <p className="mt-1 text-3xl font-semibold text-[var(--text)]">
                    {total.toFixed(2)} {item.unit}
                  </p>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <MetricPill label="En lot" value={inLot} unit={item.unit} tone="danger" />
                    <MetricPill label="Restant" value={remaining} unit={item.unit} tone={isCritical ? "danger" : "success"} />
                  </div>

                  <div className="mt-3 h-2.5 rounded-full bg-[#E8E3DB]">
                    <div className={`h-2.5 rounded-full ${barClass}`} style={{ width: `${progress}%` }} />
                  </div>
                </article>
              );
            })
          )}
        </section>
      ) : (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "70ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Stock total</th>
                  <th className="px-5 py-3.5">Collecté</th>
                  <th className="px-5 py-3.5">En lot</th>
                  <th className="px-5 py-3.5">Restant</th>
                  <th className="px-5 py-3.5">Statut</th>
                </tr>
              </thead>
              <tbody>
                {filteredByUrgency.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-4 text-center text-sm text-[var(--muted)]">
                      Aucun stock enregistré à afficher pour ce filtre.
                    </td>
                  </tr>
                ) : (
                  filteredByUrgency.map((item) => {
                    const remainingKg = remainingKgForProduct(item);
                    const isCritical = isCriticalStock(item.total_stock_kg, remainingKg);
                    const collected = fromKg(collectedByProductKg.get(item.product_id) ?? 0, item.unit);
                    const remainingDisplay = fromKg(remainingKg, item.unit);
                    return (
                      <tr key={item.product_id}>
                        <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                        <td className="px-5 py-4">{item.total_stock.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">{collected.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-[var(--danger)]">{item.reserved_in_lots.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 font-medium">{remainingDisplay.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${isCritical ? "bg-[#FFEDEE] text-[#A83C3C]" : "bg-[#EAF8EE] text-[#0F7A3B]"}`}>
                            {isCritical ? "Critique" : "Stable"}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="premium-card reveal mt-4 rounded-2xl p-6" style={{ ["--delay" as string]: "120ms" }}>
        <h3 className="mb-4 text-lg font-semibold text-[var(--text)]">Journal des mouvements</h3>
        <div className="overflow-x-auto">
          <table className="wf-table min-w-full text-left text-sm">
            <thead>
              <tr>
                <th className="px-5 py-3.5">Date</th>
                <th className="px-5 py-3.5">Produit</th>
                <th className="px-5 py-3.5">Mouvement</th>
                <th className="px-5 py-3.5">Raison</th>
                <th className="px-5 py-3.5">Avant</th>
                <th className="px-5 py-3.5">Après</th>
                <th className="px-5 py-3.5">Référence</th>
              </tr>
            </thead>
            <tbody>
              {movementRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-4 text-center text-sm text-[var(--muted)]">
                    Aucun mouvement disponible pour ce filtre.
                  </td>
                </tr>
              ) : (
                movementRows.map((event) => {
                  const stock = stockByProduct.get(event.product_id);
                  const unit = stock?.unit ?? "kg";
                  const signed = event.delta_kg >= 0 ? "+" : "-";
                  const delta = fromKg(Math.abs(event.delta_kg), unit);
                  const before = fromKg(event.before_kg, unit);
                  const after = fromKg(event.after_kg, unit);
                  return (
                    <tr key={event.id}>
                      <td className="px-5 py-4 text-xs text-[var(--muted)]">{formatDateTime(event.date)}</td>
                      <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(event.product_id) ?? event.product_id.slice(0, 8)}</td>
                      <td className={`px-5 py-4 font-semibold ${event.delta_kg >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                        {signed}{delta.toFixed(2)} {unit}
                      </td>
                      <td className="px-5 py-4">{movementReasonLabel(event.reason)}</td>
                      <td className="px-5 py-4 text-[var(--muted)]">{before.toFixed(2)} {unit}</td>
                      <td className="px-5 py-4 font-medium text-[var(--text)]">{after.toFixed(2)} {unit}</td>
                      <td className="px-5 py-4 text-xs text-[var(--muted)]">
                        <span className="font-semibold text-[var(--text)]">{event.reference}</span>
                        {event.note ? ` · ${event.note}` : ""}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {filtered.length === 0 && (
        <section className="premium-card reveal mt-4 rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun stock enregistré. Les lignes de stock sont créées automatiquement via les collectes.</p>
        </section>
      )}
    </main>
  );
}

function MetricPill({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: number;
  unit: string;
  tone: "neutral" | "info" | "success" | "danger";
}) {
  const toneClass =
    tone === "danger"
      ? "bg-[#FFEDEE] text-[var(--danger)]"
      : tone === "success"
        ? "bg-[#EAF8EE] text-[var(--success)]"
        : tone === "info"
          ? "bg-[#EEF5FF] text-[var(--text)]"
          : "bg-[var(--surface-soft)] text-[var(--text)]";
  return (
    <div className={`rounded-lg px-2 py-1.5 ${toneClass}`}>
      <p className="font-semibold">
        {value.toFixed(2)} {unit}
      </p>
      <p>{label}</p>
    </div>
  );
}

function isCriticalStock(totalStockKg: number, remainingKg: number) {
  if (totalStockKg <= 0) return false;
  return remainingKg < totalStockKg * 0.2;
}

function stockUrgencyScore(totalStockKg: number, remainingKg: number) {
  if (totalStockKg <= 0) return 1;
  return remainingKg / totalStockKg;
}

function normalizeToken(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function normalizeMassUnit(unit?: string | null): "kg" | "ton" {
  return String(unit || "kg").toLowerCase() === "ton" ? "ton" : "kg";
}

function toKg(value: number, unit?: string | null) {
  return normalizeMassUnit(unit) === "ton" ? value * 1000 : value;
}

function fromKg(valueKg: number, unit?: string | null) {
  return normalizeMassUnit(unit) === "ton" ? valueKg / 1000 : valueKg;
}

function movementReasonLabel(reason: MovementReason) {
  if (reason === "collecte") return "Collecte";
  if (reason === "perte_lot") return "Perte lot";
  if (reason === "sortie_lot") return "Sortie lot";
  return "Commercialisation";
}

function isExitReason(stepType: string) {
  const value = normalizeToken(stepType);
  return ["vente", "sale", "livraison", "delivery", "transfert", "transfer", "expedition", "sortie"].some((token) =>
    value.includes(token),
  );
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
