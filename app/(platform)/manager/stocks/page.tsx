"use client";

import { useMemo, useState } from "react";
import { AIInsightsStrip, type AIInsightItem } from "@/components/ui/AIInsightsStrip";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useBatches } from "@/hooks/useBatches";
import { useCatalogProducts, useCommercialOrders } from "@/hooks/useCommercial";
import { useInputs } from "@/hooks/useInputs";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import type { Stock } from "@/lib/api/types";

type ViewMode = "cards" | "table";
type LogOrder = "newest" | "oldest";
type MovementReason = "collecte" | "lot" | "commercialisation";

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

  const filtered = useMemo(() => {
    return stocks.filter((item) => (productId === "Tous" ? true : item.product_id === productId));
  }, [stocks, productId]);

  const filteredByUrgency = useMemo(() => {
    return filtered.slice().sort((a, b) => stockUrgencyScore(a) - stockUrgencyScore(b));
  }, [filtered]);

  const criticalCount = useMemo(() => filtered.filter((item) => isCriticalStock(item)).length, [filtered]);

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

    for (const batch of batches) {
      const qtyKg = toKg(batch.initial_qty, batch.unit);
      events.push({
        id: `lot-${batch.id}`,
        product_id: batch.product_id,
        date: batch.created_at || `${batch.creation_date}T00:00:00Z`,
        quantity_kg: qtyKg,
        delta_kg: -qtyKg,
        reason: "lot",
        reference: batch.code,
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
  }, [batches, catalogById, inputs, orders, productByNormalizedName]);

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

  const stockInsights = useMemo<AIInsightItem[]>(() => {
    const trackedCount = filtered.length;
    const critical = filtered.filter((item) => isCriticalStock(item));
    const avgRemainingRatio =
      filtered.length > 0
        ? filtered.reduce((sum, item) => {
            const total = item.total_stock > 0 ? item.total_stock : 1;
            return sum + item.available_stock / total;
          }, 0) / filtered.length
        : 0;

    const biggestDeficit = critical
      .slice()
      .sort((a, b) => (b.total_stock * 0.2 - b.available_stock) - (a.total_stock * 0.2 - a.available_stock))[0];

    const items: AIInsightItem[] = [
      {
        id: "critical-stock-count",
        title: critical.length > 0 ? "Rupture potentielle detectee" : "Stock global stable",
        message:
          critical.length > 0
            ? `${critical.length}/${trackedCount} produit(s) sous seuil critique.`
            : `${trackedCount} produit(s) suivis sans alerte critique.`,
        tone: critical.length > 0 ? "critical" : "success",
        actionLabel: "Ouvrir recommandations IA",
        href: "/manager/lots?tab=recommendations",
      },
      {
        id: "remaining-ratio",
        title: "Pression stock",
        message: `Niveau moyen restant: ${(avgRemainingRatio * 100).toFixed(1)}% du stock total.`,
        tone: avgRemainingRatio < 0.3 ? "warning" : "info",
        meta: avgRemainingRatio < 0.3 ? "Replanifier collectes et lots pour eviter rupture." : "Marge exploitable pour les prochains lots.",
      },
    ];

    if (biggestDeficit) {
      items.push({
        id: "top-deficit",
        title: "Produit le plus expose",
        message: `${productLookup.get(biggestDeficit.product_id) ?? biggestDeficit.product_id.slice(0, 8)} sous seuil de securite.`,
        tone: "warning",
        meta: `Restant ${biggestDeficit.available_stock.toFixed(2)} ${biggestDeficit.unit} pour un seuil critique de ${(biggestDeficit.total_stock * 0.2).toFixed(2)} ${biggestDeficit.unit}.`,
      });
    }

    return items.slice(0, 4);
  }, [filtered, productLookup]);

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

      <AIInsightsStrip
        title="Insights IA stock"
        subtitle="Priorites operationnelles basees sur le niveau et la dynamique de stock."
        items={stockInsights}
      />

      {viewMode === "cards" ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filteredByUrgency.length === 0 ? (
            <article className="premium-card reveal rounded-2xl p-5 sm:col-span-2 xl:col-span-3" style={{ ["--delay" as string]: "70ms" }}>
              <p className="text-sm text-[var(--muted)]">Aucun produit de stock à afficher pour ce filtre.</p>
            </article>
          ) : (
            filteredByUrgency.map((item, index) => {
              const isCritical = isCriticalStock(item);
              const total = item.total_stock;
              const inLot = item.reserved_in_lots;
              const remaining = item.available_stock;
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
                    const isCritical = isCriticalStock(item);
                    const collected = fromKg(collectedByProductKg.get(item.product_id) ?? 0, item.unit);
                    return (
                      <tr key={item.product_id}>
                        <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                        <td className="px-5 py-4">{item.total_stock.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">{collected.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-[var(--danger)]">{item.reserved_in_lots.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 font-medium">{item.available_stock.toFixed(2)} {item.unit}</td>
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

function isCriticalStock(item: Stock) {
  if (item.total_stock_kg <= 0) return false;
  return item.available_stock_kg < item.total_stock_kg * 0.2;
}

function stockUrgencyScore(item: Stock) {
  if (item.total_stock_kg <= 0) return 1;
  return item.available_stock_kg / item.total_stock_kg;
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
  if (reason === "lot") return "Lot";
  return "Commercialisation";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
