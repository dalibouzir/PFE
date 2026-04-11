"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { lotStageHistoryByCode, lots, productFilters, type LotRecord, type LotStatus, type ProductName } from "@/lib/mock-data";

const statusTone: Record<LotStatus, "success" | "warning" | "info" | "danger"> = {
  Collecte: "info",
  "En transformation": "warning",
  Pret: "success",
  Bloque: "danger",
};

export default function LotsPage() {
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [selectedLot, setSelectedLot] = useState<LotRecord | null>(lots[0]);

  const filtered = useMemo(() => {
    return lots.filter((item) => (product === "Tous" ? true : item.produit === product));
  }, [product]);

  const selectedHistory = selectedLot ? lotStageHistoryByCode[selectedLot.code] ?? [] : [];

  return (
    <main>
      <PageIntro title="Lots" subtitle="Suivi des lots, progression et demarrage transformation." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="flex flex-wrap items-center gap-2">
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
          <button className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Creer lot
          </button>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <article className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Code lot</th>
                  <th className="px-4 py-3">Produit</th>
                  <th className="px-4 py-3">Creation</th>
                  <th className="px-4 py-3">Initial</th>
                  <th className="px-4 py-3">Actuel</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3">Progression</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                    <td className="px-4 py-3 font-medium text-[var(--text)]">{item.code}</td>
                    <td className="px-4 py-3">{item.produit}</td>
                    <td className="px-4 py-3">{item.createdAt}</td>
                    <td className="px-4 py-3">{item.initialQuantityKg.toLocaleString("fr-FR")} kg</td>
                    <td className="px-4 py-3">{item.currentQuantityKg.toLocaleString("fr-FR")} kg</td>
                    <td className="px-4 py-3">
                      <StatusBadge label={item.status} tone={statusTone[item.status]} />
                    </td>
                    <td className="px-4 py-3 min-w-[160px]">
                      <div className="h-2 rounded-full bg-[#e2ede4]">
                        <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${item.progressionPct}%` }} />
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--muted)]">{item.progressionPct}%</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1 text-xs">
                        <button className="text-left font-semibold text-[var(--green-700)] hover:underline" onClick={() => setSelectedLot(item)}>
                          Voir detail
                        </button>
                        <button className="text-left text-[var(--muted)] hover:text-[var(--green-700)]">Demarrer transformation</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "130ms" }}>
          {selectedLot ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-base font-semibold text-[var(--green-900)]">Detail {selectedLot.code}</h3>
                <StatusBadge label={selectedLot.status} tone={statusTone[selectedLot.status]} />
              </div>

              <div className="grid gap-2 text-sm sm:grid-cols-2">
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-xs text-[var(--muted)]">Produit</p>
                  <p className="font-semibold text-[var(--text)]">{selectedLot.produit}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-xs text-[var(--muted)]">Grade dominant</p>
                  <p className="font-semibold text-[var(--text)]">{selectedLot.gradeDominant}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-xs text-[var(--muted)]">Membre source</p>
                  <p className="font-semibold text-[var(--text)]">{selectedLot.memberNom}</p>
                </div>
                <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                  <p className="text-xs text-[var(--muted)]">Rendement actuel</p>
                  <p className="font-semibold text-[var(--text)]">{((selectedLot.currentQuantityKg / selectedLot.initialQuantityKg) * 100).toFixed(1)}%</p>
                </div>
              </div>

              <div className="mt-4">
                <h4 className="text-sm font-semibold text-[var(--green-900)]">Historique etapes</h4>
                <div className="mt-2 space-y-2">
                  {selectedHistory.length === 0 && <p className="text-xs text-[var(--muted)]">Aucune etape enregistree.</p>}
                  {selectedHistory.map((step) => (
                    <div key={step.stage} className="rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-[var(--text)]">{step.stage}</p>
                        <StatusBadge
                          label={step.state === "termine" ? "Termine" : step.state === "en cours" ? "En cours" : "A venir"}
                          tone={step.state === "termine" ? "success" : step.state === "en cours" ? "warning" : "info"}
                        />
                      </div>
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        Debut: {step.startedAt} · Fin: {step.endedAt ?? "-"} · Rendement: {step.rendementPct.toFixed(1)}%
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-[var(--muted)]">Selectionnez un lot.</p>
          )}
        </article>
      </section>
    </main>
  );
}
