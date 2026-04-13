"use client";

import { FormEvent, useMemo, useState } from "react";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  gradeFilters,
  inputsHistory,
  members,
  productFilters,
  type Grade,
  type InputRecord,
  type InputStatus,
  type ProductName,
} from "@/lib/mock-data";

const statusTone: Record<InputStatus, "success" | "warning" | "info"> = {
  Valide: "success",
  "Controle qualite": "warning",
  "En attente": "info",
};

const basePriceByProduct: Record<ProductName, number> = {
  Mangue: 330,
  Arachide: 240,
  Mil: 190,
};

const gradeMultiplier: Record<Grade, number> = {
  A: 1.12,
  B: 1,
  C: 0.82,
};

const currency = new Intl.NumberFormat("fr-SN", { maximumFractionDigits: 0 });

type InputFormState = {
  date: string;
  memberId: string;
  produit: ProductName;
  grade: Grade;
  quantiteKg: string;
  statut: InputStatus;
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function buildForm(): InputFormState {
  return {
    date: todayIsoDate(),
    memberId: members[0]?.id ?? "",
    produit: "Mangue",
    grade: "A",
    quantiteKg: "900",
    statut: "En attente",
  };
}

export default function InputsPage() {
  const [records, setRecords] = useState<InputRecord[]>(inputsHistory);
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [grade, setGrade] = useState<"Tous" | Grade>("Tous");
  const [fromDate, setFromDate] = useState("");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [openModal, setOpenModal] = useState(false);
  const [form, setForm] = useState<InputFormState>(buildForm());
  const [formError, setFormError] = useState("");

  const filtered = useMemo(() => {
    return records.filter((item) => {
      const byProduct = product === "Tous" || item.produit === product;
      const byGrade = grade === "Tous" || item.grade === grade;
      const byDate = fromDate ? item.date >= fromDate : true;
      return byProduct && byGrade && byDate;
    });
  }, [records, product, grade, fromDate]);

  const totalKg = filtered.reduce((sum, item) => sum + item.quantiteKg, 0);
  const totalValue = filtered.reduce((sum, item) => sum + item.valeurEstimeeFcfa, 0);
  const pendingCount = filtered.filter((item) => item.statut !== "Valide").length;

  const estimatedValue = useMemo(() => {
    const qty = Number(form.quantiteKg);
    if (!Number.isFinite(qty) || qty <= 0) return 0;
    return Math.round(qty * basePriceByProduct[form.produit] * gradeMultiplier[form.grade]);
  }, [form.quantiteKg, form.produit, form.grade]);

  const openCreateModal = () => {
    setForm(buildForm());
    setFormError("");
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError("");
  };

  const submitForm = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const quantity = Number(form.quantiteKg);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setFormError("La quantite doit etre superieure a 0.");
      return;
    }

    const member = members.find((item) => item.id === form.memberId);
    if (!member) {
      setFormError("Selectionnez un membre valide.");
      return;
    }

    const idSuffix = `${form.date.replaceAll("-", "").slice(2)}-${String(records.length + 1).padStart(2, "0")}`;

    const created: InputRecord = {
      id: `INP-${idSuffix}`,
      date: form.date,
      membre: member.nom,
      memberId: member.id,
      produit: form.produit,
      quantiteKg: quantity,
      grade: form.grade,
      valeurEstimeeFcfa: estimatedValue,
      statut: form.statut,
    };

    setRecords((prev) => [created, ...prev]);
    closeModal();
  };

  return (
    <main>
      <PageIntro title="Inputs" subtitle="Collectes interactives, calcul automatique et edition locale des enregistrements." />

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
          <button onClick={openCreateModal} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Ajouter input
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Volume visible</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{totalKg.toLocaleString("fr-FR")} kg</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Valeur estimee</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{currency.format(totalValue)} FCFA</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">A traiter</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{pendingCount}</p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "100ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune collecte ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
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
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${100 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.membre}</p>
                  <p className="text-xs text-[var(--muted)]">{item.id} · {item.date}</p>
                </div>
                <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Produit</p>
                  <p className="font-semibold text-[var(--green-900)]">{item.produit}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Grade</p>
                  <p className="font-semibold text-[var(--green-900)]">{item.grade}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Quantite</p>
                  <p className="font-semibold text-[var(--green-900)]">{item.quantiteKg.toLocaleString("fr-FR")} kg</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Valeur</p>
                  <p className="font-semibold text-[var(--green-900)]">{currency.format(item.valeurEstimeeFcfa)} FCFA</p>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title="Nouvelle collecte"
        subtitle="Enregistrement local instantane avec estimation automatique de la valeur."
        size="xl"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button className="soft-focus w-full rounded-xl border border-white/85 bg-white/55 px-4 py-2 text-sm text-[var(--green-900)] hover:bg-white/75 sm:w-auto" onClick={closeModal} type="button">
              Annuler
            </button>
            <button className="soft-focus w-full rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)] sm:w-auto" form="input-form" type="submit">
              Enregistrer
            </button>
          </div>
        }
      >
        <form id="input-form" onSubmit={submitForm} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm text-[var(--muted)]">
            Date
            <input
              type="date"
              value={form.date}
              onChange={(event) => setForm((prev) => ({ ...prev, date: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Membre
            <select
              value={form.memberId}
              onChange={(event) => setForm((prev) => ({ ...prev, memberId: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.nom}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)]">
            Produit
            <select
              value={form.produit}
              onChange={(event) => setForm((prev) => ({ ...prev, produit: event.target.value as ProductName }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {productFilters.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)]">
            Quantite (kg)
            <input
              type="number"
              min={1}
              value={form.quantiteKg}
              onChange={(event) => setForm((prev) => ({ ...prev, quantiteKg: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="Ex: 950"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Grade
            <select
              value={form.grade}
              onChange={(event) => setForm((prev) => ({ ...prev, grade: event.target.value as Grade }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {gradeFilters.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)]">
            Statut
            <select
              value={form.statut}
              onChange={(event) => setForm((prev) => ({ ...prev, statut: event.target.value as InputStatus }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              <option>En attente</option>
              <option>Controle qualite</option>
              <option>Valide</option>
            </select>
          </label>

          <div className="rounded-xl border border-[#d7e8d8] bg-[linear-gradient(135deg,rgba(248,252,248,0.92),rgba(234,245,236,0.86))] p-3 sm:col-span-2 lg:col-span-3">
            <p className="text-xs text-[var(--muted)]">Estimation automatique</p>
            <p className="mt-1 text-lg font-semibold text-[var(--green-900)]">{currency.format(estimatedValue)} FCFA</p>
            <p className="mt-1 text-[11px] text-[var(--muted)]">
              Base {basePriceByProduct[form.produit]} FCFA/kg x coef grade {gradeMultiplier[form.grade].toFixed(2)}
            </p>
          </div>

          {formError && <p className="rounded-xl border border-[#ecc9c9] bg-[#fff1f1]/90 px-3 py-2 text-xs text-[#8d3d3d] sm:col-span-2 lg:col-span-3">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
