"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { gradeFilters, inputsHistory, members, productFilters, type Grade, type InputStatus, type ProductName } from "@/lib/mock-data";

const statusTone: Record<InputStatus, "success" | "warning" | "info"> = {
  Valide: "success",
  "Controle qualite": "warning",
  "En attente": "info",
};

const currency = new Intl.NumberFormat("fr-SN", { maximumFractionDigits: 0 });

export default function InputsPage() {
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [grade, setGrade] = useState<"Tous" | Grade>("Tous");
  const [fromDate, setFromDate] = useState("");
  const [openModal, setOpenModal] = useState(false);

  const filtered = useMemo(() => {
    return inputsHistory.filter((item) => {
      const byProduct = product === "Tous" || item.produit === product;
      const byGrade = grade === "Tous" || item.grade === grade;
      const byDate = fromDate ? item.date >= fromDate : true;
      return byProduct && byGrade && byDate;
    });
  }, [product, grade, fromDate]);

  return (
    <main>
      <PageIntro title="Inputs" subtitle="Collectes recentes et enregistrement rapide." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto]">
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
            value={grade}
            onChange={(event) => setGrade(event.target.value as "Tous" | Grade)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous grades</option>
            {gradeFilters.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <input
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          />
          <button
            onClick={() => setOpenModal(true)}
            className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
          >
            Ajouter input
          </button>
        </div>
      </section>

      <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "100ms" }}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Membre</th>
                <th className="px-4 py-3">Produit</th>
                <th className="px-4 py-3">Quantite</th>
                <th className="px-4 py-3">Grade</th>
                <th className="px-4 py-3">Valeur estimee</th>
                <th className="px-4 py-3">Statut</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/65">
                  <td className="px-4 py-3">{item.date}</td>
                  <td className="px-4 py-3 font-medium text-[var(--text)]">{item.membre}</td>
                  <td className="px-4 py-3">{item.produit}</td>
                  <td className="px-4 py-3">{item.quantiteKg.toLocaleString("fr-FR")} kg</td>
                  <td className="px-4 py-3">{item.grade}</td>
                  <td className="px-4 py-3">{currency.format(item.valeurEstimeeFcfa)} FCFA</td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {openModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#103126]/45 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-2xl rounded-2xl border border-[var(--line)] bg-white p-5 shadow-[0_30px_50px_rgba(15,47,34,0.24)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--green-900)]">Nouvelle collecte</h3>
                <p className="text-sm text-[var(--muted)]">Creation locale (pas de backend)</p>
              </div>
              <button className="text-[var(--muted)] hover:text-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Fermer
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <label className="text-sm text-[var(--muted)]">
                Date
                <input type="date" defaultValue="2026-04-11" className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" />
              </label>
              <label className="text-sm text-[var(--muted)]">
                Membre
                <select className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  {members.map((member) => (
                    <option key={member.id}>{member.nom}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-[var(--muted)]">
                Produit
                <select className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  {productFilters.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-[var(--muted)]">
                Quantite (kg)
                <input type="number" placeholder="Ex: 950" className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" />
              </label>
              <label className="text-sm text-[var(--muted)]">
                Grade
                <select className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  {gradeFilters.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-[var(--muted)]">
                Valeur estimee (FCFA)
                <input type="number" placeholder="Ex: 210000" className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" />
              </label>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm" onClick={() => setOpenModal(false)}>
                Annuler
              </button>
              <button className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
