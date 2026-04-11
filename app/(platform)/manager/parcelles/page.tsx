"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { parcels, productFilters, type ParcelRecord, type ProductName } from "@/lib/mock-data";

const statusTone: Record<ParcelRecord["statut"], "success" | "warning" | "info"> = {
  Active: "success",
  Preparation: "info",
  Repos: "warning",
};

export default function ParcellesPage() {
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [status, setStatus] = useState<"Tous" | ParcelRecord["statut"]>("Tous");

  const filtered = useMemo(() => {
    return parcels.filter((item) => {
      const byProduct = product === "Tous" || item.cultureActuelle === product;
      const byStatus = status === "Tous" || item.statut === status;
      const text = `${item.code} ${item.memberNom} ${item.localisation}`.toLowerCase();
      return byProduct && byStatus && text.includes(query.toLowerCase());
    });
  }, [query, product, status]);

  return (
    <main>
      <PageIntro title="Parcelles" subtitle="Suivi des parcelles, sols et cultures en cours." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr_1fr]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Code parcelle, membre, localisation..."
          />
          <select
            value={product}
            onChange={(event) => setProduct(event.target.value as "Tous" | ProductName)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            {productFilters.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as "Tous" | ParcelRecord["statut"])}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option>Active</option>
            <option>Preparation</option>
            <option>Repos</option>
          </select>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${80 + index * 30}ms` }}>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-[var(--green-900)]">{item.code}</p>
                <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
              </div>
              <p className="text-sm text-[var(--text)]">{item.memberNom}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">{item.localisation}</p>

              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl bg-[var(--surface-soft)] p-2.5">
                  <p className="text-[11px] text-[var(--muted)]">Superficie</p>
                  <p className="font-semibold text-[var(--text)]">{item.superficieHa.toFixed(1)} ha</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-soft)] p-2.5">
                  <p className="text-[11px] text-[var(--muted)]">Type sol</p>
                  <p className="font-semibold text-[var(--text)]">{item.typeSol}</p>
                </div>
              </div>

              <div className="mt-3 rounded-xl border border-[var(--line)] px-3 py-2 text-xs text-[var(--muted)]">
                Culture actuelle: <span className="font-semibold text-[var(--green-900)]">{item.cultureActuelle}</span>
              </div>
            </article>
          ))}
        </div>

        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "160ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Vue zone</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">Apercu parcelles Thies, Louga, Casamance</p>

          <div className="mt-3 rounded-2xl border border-[var(--line)] bg-[linear-gradient(180deg,#f1f6f2_0%,#e7f0ea_100%)] p-3">
            <div className="h-52 rounded-xl border border-dashed border-[#bcd3be] bg-[radial-gradient(circle_at_30%_30%,rgba(112,170,128,0.18),transparent_42%),radial-gradient(circle_at_70%_60%,rgba(84,161,115,0.2),transparent_45%)]" />
            <p className="mt-2 text-[11px] text-[var(--muted)]">Placeholder carte legere pour extension geographique.</p>
          </div>

          <div className="mt-3 space-y-2 text-sm">
            <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2">Parcelles actives: {parcels.filter((item) => item.statut === "Active").length}</div>
            <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2">Superficie totale: {parcels.reduce((acc, item) => acc + item.superficieHa, 0).toFixed(1)} ha</div>
          </div>
        </article>
      </section>
    </main>
  );
}
