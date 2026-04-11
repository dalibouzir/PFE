"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { productFilters, stockRecords, type ProductName, type StockStatus } from "@/lib/mock-data";

const statusTone: Record<StockStatus, "success" | "warning" | "danger"> = {
  Correct: "success",
  "A surveiller": "warning",
  Critique: "danger",
};

export default function StocksPage() {
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [status, setStatus] = useState<"Tous" | StockStatus>("Tous");

  const filtered = useMemo(() => {
    return stockRecords.filter((item) => {
      const byProduct = product === "Tous" || item.produit === product;
      const byStatus = status === "Tous" || item.statut === status;
      return byProduct && byStatus;
    });
  }, [product, status]);

  const criticalCount = filtered.filter((item) => item.statut === "Critique").length;

  return (
    <main>
      <PageIntro title="Stocks" subtitle="Niveaux de stock, seuils et alertes critiques." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
          <select
            value={product}
            onChange={(event) => setProduct(event.target.value as "Tous" | ProductName)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous produits</option>
            {productFilters.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as "Tous" | StockStatus)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous statuts</option>
            <option>Correct</option>
            <option>A surveiller</option>
            <option>Critique</option>
          </select>
          <div className="rounded-xl border border-[#f2d4cd] bg-[#fff3f0] px-3 py-2 text-sm text-[#9f463e]">
            Alertes critiques: <span className="font-semibold">{criticalCount}</span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {productFilters.map((item, index) => {
          const byProduct = stockRecords.filter((stock) => stock.produit === item);
          const total = byProduct.reduce((acc, stock) => acc + stock.quantiteTonnes, 0);
          const threshold = byProduct.reduce((acc, stock) => acc + stock.seuilTonnes, 0);
          const ratio = Math.min((total / threshold) * 100, 100);

          return (
            <article key={item} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${80 + index * 40}ms` }}>
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-[var(--green-900)]">{item}</h3>
                <p className="text-xs text-[var(--muted)]">{byProduct.length} references</p>
              </div>
              <p className="mt-2 text-xl font-semibold text-[var(--green-900)]">{total.toFixed(1)} t</p>
              <p className="text-xs text-[var(--muted)]">Seuil cumule {threshold.toFixed(1)} t</p>
              <div className="mt-3 h-2 rounded-full bg-[#e4eee6]">
                <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${ratio}%` }} />
              </div>
            </article>
          );
        })}
      </section>

      <section className="premium-card reveal mt-4 overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "220ms" }}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Produit</th>
                <th className="px-4 py-3">Grade</th>
                <th className="px-4 py-3">Quantite</th>
                <th className="px-4 py-3">Seuil</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Entrepot</th>
                <th className="px-4 py-3">Maj</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                  <td className="px-4 py-3 font-medium text-[var(--text)]">{item.produit}</td>
                  <td className="px-4 py-3">{item.grade}</td>
                  <td className="px-4 py-3">{item.quantiteTonnes.toFixed(1)} t</td>
                  <td className="px-4 py-3">{item.seuilTonnes.toFixed(1)} t</td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
                  </td>
                  <td className="px-4 py-3">{item.entrepot}</td>
                  <td className="px-4 py-3 text-xs text-[var(--muted)]">{item.derniereMiseAJour}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
