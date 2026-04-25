"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import type { Stock } from "@/lib/api/types";

export default function StocksPage() {
  const { data: stocks = [] } = useStocks();
  const { data: products = [] } = useProducts();

  const [productId, setProductId] = useState<string>("Tous");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");

  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);

  const filtered = useMemo(() => {
    return stocks.filter((item) => (productId === "Tous" ? true : item.product_id === productId));
  }, [stocks, productId]);

  const criticalCount = filtered.filter((item) => isCriticalStock(item)).length;

  const stockCards = useMemo(() => {
    return filtered
      .slice()
      .sort((a, b) => stockUrgencyScore(a) - stockUrgencyScore(b))
      .slice(0, 6);
  }, [filtered]);

  return (
    <main>
      <PageIntro
        title="Stocks"
        subtitle="Total collectes et stock disponible apres lots. Critique si disponible < 20% du total."
      />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
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
          <div className="flex items-center gap-3">
            <div className="rounded-xl border border-[#E8B9B9] bg-[#FFEDEE] px-3 py-2 text-sm text-[var(--danger)]">
              Alertes critiques: <span className="font-semibold">{criticalCount}</span>
            </div>
            <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-1">
              <button
                onClick={() => setViewMode("cards")}
                className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "cards" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
              >
                📱
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "table" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
              >
                📊
              </button>
            </div>
          </div>
        </div>
      </section>

      {viewMode === "cards" ? (
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {stockCards.length === 0 ? (
          <article className="premium-card reveal rounded-2xl p-5 sm:col-span-2 xl:col-span-3" style={{ ["--delay" as string]: "70ms" }}>
            <p className="text-sm text-[var(--muted)]">Aucun produit de stock a afficher pour ce filtre.</p>
          </article>
        ) : (
          stockCards.map((item, index) => {
            const isCritical = isCriticalStock(item);
            const total = item.total_stock;
            const available = item.available_stock;
            const threshold = total * 0.2;
            const progress = total > 0 ? Math.max(6, Math.min((available / total) * 100, 100)) : 0;
            const barClass = isCritical
              ? "bg-gradient-to-r from-red-400 to-red-600"
              : total > 0 && available < threshold * 1.4
                ? "bg-gradient-to-r from-amber-400 to-amber-600"
                : "bg-gradient-to-r from-green-400 to-green-600";
            return (
              <article key={item.product_id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${70 + index * 25}ms` }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                    <p className="text-xs text-[var(--muted)]">Critique si &lt; 20% du total</p>
                  </div>
                  <StatusBadge label={isCritical ? "Critique" : "Stable"} tone={isCritical ? "danger" : "success"} />
                </div>
                <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">Disponible</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--text)]">{available.toFixed(2)} {item.unit}</p>
                <p className={`mt-1 text-xs font-semibold ${isCritical ? "text-[var(--danger)]" : "text-[var(--success)]"}`}>
                  {isCritical ? "Stock faible" : "Stock stable"} · Total {total.toFixed(2)} {item.unit}
                </p>
                <div className="mt-3 h-2.5 rounded-full bg-[#E8E3DB]">
                  <div className={`h-2.5 rounded-full ${barClass}`} style={{ width: `${progress}%` }} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-[#EEF5FF] px-2 py-1.5">
                    <p className="font-semibold text-[var(--text)]">{total.toFixed(2)}</p>
                    <p className="text-[var(--muted)]">Total</p>
                  </div>
                  <div className="rounded-lg bg-[#FFEDEE] px-2 py-1.5 text-[var(--danger)]">
                    <p className="font-semibold">{item.reserved_in_lots.toFixed(2)}</p>
                    <p className="text-[var(--danger)]">Sortie</p>
                  </div>
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
                <th className="px-5 py-3.5">Total</th>
                <th className="px-5 py-3.5">Disponible</th>
                <th className="px-5 py-3.5">Réservé</th>
                <th className="px-5 py-3.5">Remplissage</th>
                <th className="px-5 py-3.5">Statut</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-4 text-center text-sm text-[var(--muted)]">
                    Aucun stock enregistré à afficher pour ce filtre.
                  </td>
                </tr>
              ) : (
                filtered.map((item) => {
                  const isCritical = isCriticalStock(item);
                  const fillRate = item.total_stock > 0 ? (item.available_stock / item.total_stock) * 100 : 0;
                  return (
                    <tr key={item.product_id}>
                      <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                      <td className="px-5 py-4">{item.total_stock.toFixed(2)} {item.unit}</td>
                      <td className="px-5 py-4 font-medium">{item.available_stock.toFixed(2)} {item.unit}</td>
                      <td className="px-5 py-4 text-[var(--danger)]">{item.reserved_in_lots.toFixed(2)} {item.unit}</td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-16 rounded-full bg-[#E8E3DB]">
                            <div 
                              className={`h-2 rounded-full ${isCritical ? "bg-red-500" : fillRate < 30 ? "bg-amber-500" : "bg-green-500"}`}
                              style={{ width: `${Math.min(100, fillRate)}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-[var(--muted)]">{fillRate.toFixed(0)}%</span>
                        </div>
                      </td>
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

      {filtered.length === 0 ? (
        <section className="premium-card reveal mt-4 rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun stock enregistre. Les lignes de stock sont creees automatiquement via les collectes.</p>
        </section>
      ) : (
        <section className="premium-card reveal mt-4 rounded-2xl p-6" style={{ ["--delay" as string]: "120ms" }}>
          <h3 className="mb-4 text-lg font-semibold text-[var(--text)]">📊 Récemment modifiés</h3>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Disponible</th>
                  <th className="px-5 py-3.5">Total</th>
                  <th className="px-5 py-3.5">Réservé</th>
                  <th className="px-5 py-3.5">Dernier changement</th>
                </tr>
              </thead>
              <tbody>
                {filtered
                  .slice()
                  .sort((a, b) => new Date(b.last_updated ?? 0).getTime() - new Date(a.last_updated ?? 0).getTime())
                  .map((item) => {
                    const lastUpdate = item.last_updated ? new Date(item.last_updated) : new Date();
                    const now = new Date();
                    const diffMs = now.getTime() - lastUpdate.getTime();
                    const diffMins = Math.floor(diffMs / 60000);
                    const diffHours = Math.floor(diffMs / 3600000);
                    const diffDays = Math.floor(diffMs / 86400000);
                    
                    let timeAgo = "";
                    if (diffMins < 1) timeAgo = "À l'instant";
                    else if (diffMins < 60) timeAgo = `${diffMins} min`;
                    else if (diffHours < 24) timeAgo = `${diffHours}h`;
                    else if (diffDays < 30) timeAgo = `${diffDays}j`;
                    else timeAgo = lastUpdate.toLocaleDateString("fr-FR");

                    return (
                      <tr key={item.id}>
                        <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                        <td className="px-5 py-4">{item.available_stock.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">{item.total_stock.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-[var(--danger)]">{item.reserved_in_lots.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-xs text-[var(--muted)]">{timeAgo}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
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
