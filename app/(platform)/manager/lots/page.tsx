"use client";

import { FormEvent, useMemo, useState } from "react";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  gradeFilters,
  lotStageHistoryByCode,
  lots,
  productFilters,
  type Grade,
  type LotRecord,
  type LotStageHistory,
  type LotStatus,
  type ProductName,
  type StageName,
} from "@/lib/mock-data";

const statusTone: Record<LotStatus, "success" | "warning" | "info" | "danger"> = {
  Collecte: "info",
  "En transformation": "warning",
  Pret: "success",
  Bloque: "danger",
};

const stageTone: Record<LotStageHistory["state"], "success" | "warning" | "info"> = {
  termine: "success",
  "en cours": "warning",
  "a venir": "info",
};

const stageLabel: Record<StageName, string> = {
  nettoyage: "Nettoyage",
  sechage: "Sechage",
  tri: "Tri",
  emballage: "Emballage",
};

const productCode: Record<ProductName, string> = {
  Mangue: "MG",
  Arachide: "AR",
  Mil: "ML",
};

type LotFormState = {
  date: string;
  produit: ProductName;
  memberNom: string;
  gradeDominant: Grade;
  initialQuantityKg: string;
  status: LotStatus;
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function buildForm(): LotFormState {
  return {
    date: todayIsoDate(),
    produit: "Mangue",
    memberNom: "",
    gradeDominant: "A",
    initialQuantityKg: "1200",
    status: "Collecte",
  };
}

function formatStageStatus(state: LotStageHistory["state"]) {
  if (state === "termine") return "Termine";
  if (state === "en cours") return "En cours";
  return "A venir";
}

function createInitialHistory(status: LotStatus): LotStageHistory[] {
  if (status === "Collecte") return [];

  const base: LotStageHistory[] = [
    { stage: "nettoyage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
    { stage: "sechage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
    { stage: "tri", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
    { stage: "emballage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
  ];

  if (status === "Bloque") {
    return base.map((step, index) => {
      if (index === 0) return { ...step, startedAt: "Aujourd hui, 08:30", endedAt: null, state: "en cours", rendementPct: 86.4 };
      return step;
    });
  }

  if (status === "Pret") {
    return base.map((step, index) => ({
      ...step,
      startedAt: `Jour ${index + 1}, 08:00`,
      endedAt: `Jour ${index + 1}, 12:00`,
      state: "termine",
      rendementPct: Number((95.8 - index * 1.2).toFixed(1)),
    }));
  }

  return base.map((step, index) => {
    if (index === 0) {
      return { ...step, startedAt: "Aujourd hui, 08:10", endedAt: "Aujourd hui, 09:00", state: "termine", rendementPct: 96.2 };
    }

    if (index === 1) {
      return { ...step, startedAt: "Aujourd hui, 09:20", endedAt: null, state: "en cours", rendementPct: 91.3 };
    }

    return step;
  });
}

function advanceHistory(history: LotStageHistory[]): LotStageHistory[] {
  if (history.length === 0) return createInitialHistory("En transformation");

  const next = history.map((step) => ({ ...step }));
  const currentIndex = next.findIndex((step) => step.state === "en cours");

  if (currentIndex >= 0) {
    next[currentIndex] = {
      ...next[currentIndex],
      state: "termine",
      endedAt: "Aujourd hui",
      rendementPct: Number(Math.max(next[currentIndex].rendementPct, 88.5).toFixed(1)),
    };

    if (currentIndex + 1 < next.length) {
      next[currentIndex + 1] = {
        ...next[currentIndex + 1],
        state: "en cours",
        startedAt: "Maintenant",
        endedAt: null,
        rendementPct: Number(Math.max(next[currentIndex + 1].rendementPct, 89.2).toFixed(1)),
      };
    }

    return next;
  }

  const firstUpcomingIndex = next.findIndex((step) => step.state === "a venir");
  if (firstUpcomingIndex >= 0) {
    next[firstUpcomingIndex] = {
      ...next[firstUpcomingIndex],
      state: "en cours",
      startedAt: "Maintenant",
      endedAt: null,
      rendementPct: Number(Math.max(next[firstUpcomingIndex].rendementPct, 90).toFixed(1)),
    };
  }

  return next;
}

export default function LotsPage() {
  const [records, setRecords] = useState<LotRecord[]>(lots);
  const [historyByCode, setHistoryByCode] = useState<Record<string, LotStageHistory[]>>(lotStageHistoryByCode);
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [status, setStatus] = useState<"Tous" | LotStatus>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [openCreateModal, setOpenCreateModal] = useState(false);
  const [form, setForm] = useState<LotFormState>(buildForm());
  const [formError, setFormError] = useState("");

  const filtered = useMemo(() => {
    return records.filter((item) => {
      const byProduct = product === "Tous" || item.produit === product;
      const byStatus = status === "Tous" || item.status === status;
      const byText = `${item.code} ${item.memberNom} ${item.produit}`.toLowerCase().includes(query.toLowerCase());
      return byProduct && byStatus && byText;
    });
  }, [records, product, status, query]);

  const selectedLot = useMemo(() => records.find((item) => item.code === selectedCode) ?? null, [records, selectedCode]);
  const selectedHistory = selectedLot ? historyByCode[selectedLot.code] ?? [] : [];

  const totalCurrentKg = filtered.reduce((sum, item) => sum + item.currentQuantityKg, 0);
  const blockedCount = filtered.filter((item) => item.status === "Bloque").length;
  const inTransformCount = filtered.filter((item) => item.status === "En transformation").length;

  const openLotDetails = (lot: LotRecord) => setSelectedCode(lot.code);

  const handleStartTransformation = (code: string) => {
    setRecords((prev) =>
      prev.map((item) => {
        if (item.code !== code) return item;
        if (item.status === "Pret") return item;

        return {
          ...item,
          status: item.status === "Bloque" ? "Bloque" : "En transformation",
          progressionPct: Math.max(item.progressionPct, 34),
        };
      }),
    );

    setHistoryByCode((prev) => {
      const current = prev[code] ?? [];
      if (current.length > 0) return prev;
      return { ...prev, [code]: createInitialHistory("En transformation") };
    });
  };

  const handleAdvanceLot = (code: string) => {
    setRecords((prev) =>
      prev.map((item) => {
        if (item.code !== code) return item;
        if (item.status === "Pret") return item;

        const nextProgress = Math.min(100, item.progressionPct + 12);
        const lossRatio = Math.max(0.07, (100 - nextProgress) / 500 + 0.06);
        const nextCurrent = Math.round(item.initialQuantityKg * (1 - lossRatio));

        return {
          ...item,
          progressionPct: nextProgress,
          currentQuantityKg: Math.max(0, nextCurrent),
          status: nextProgress >= 100 ? "Pret" : "En transformation",
        };
      }),
    );

    setHistoryByCode((prev) => ({
      ...prev,
      [code]: advanceHistory(prev[code] ?? []),
    }));
  };

  const openCreate = () => {
    setForm(buildForm());
    setFormError("");
    setOpenCreateModal(true);
  };

  const closeCreate = () => {
    setOpenCreateModal(false);
    setFormError("");
  };

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!form.memberNom.trim()) {
      setFormError("Le nom du membre source est requis.");
      return;
    }

    const initialQuantityKg = Number(form.initialQuantityKg);
    if (!Number.isFinite(initialQuantityKg) || initialQuantityKg <= 0) {
      setFormError("La quantite initiale doit etre superieure a 0.");
      return;
    }

    const sameProductCount = records.filter((item) => item.produit === form.produit).length + 1;
    const yymm = `${form.date.slice(2, 4)}${form.date.slice(5, 7)}`;
    const nextCode = `LT-${productCode[form.produit]}-${yymm}-${String(sameProductCount).padStart(2, "0")}`;

    const progressionByStatus: Record<LotStatus, number> = {
      Collecte: 12,
      "En transformation": 42,
      Pret: 100,
      Bloque: 28,
    };

    const currentQuantityKg =
      form.status === "Pret"
        ? Math.round(initialQuantityKg * 0.88)
        : form.status === "En transformation"
          ? Math.round(initialQuantityKg * 0.94)
          : initialQuantityKg;

    const created: LotRecord = {
      id: `LOT-${String(records.length + 1).padStart(3, "0")}`,
      code: nextCode,
      produit: form.produit,
      createdAt: form.date,
      initialQuantityKg,
      currentQuantityKg,
      status: form.status,
      progressionPct: progressionByStatus[form.status],
      gradeDominant: form.gradeDominant,
      memberNom: form.memberNom.trim(),
    };

    setRecords((prev) => [created, ...prev]);
    setHistoryByCode((prev) => ({
      ...prev,
      [created.code]: createInitialHistory(created.status),
    }));

    setSelectedCode(created.code);
    closeCreate();
  };

  return (
    <main>
      <PageIntro title="Lots" subtitle="Suivi avance des lots avec actions locales, progression dynamique et modals glass." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Rechercher un lot ou membre..."
          />

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
            onChange={(event) => setStatus(event.target.value as "Tous" | LotStatus)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous statuts</option>
            <option>Collecte</option>
            <option>En transformation</option>
            <option>Pret</option>
            <option>Bloque</option>
          </select>

          <button onClick={openCreate} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Creer lot
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Lots visibles</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{filtered.length}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Volume actuel</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{totalCurrentKg.toLocaleString("fr-FR")} kg</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">En risque / actif</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">
                {blockedCount} bloques · {inTransformCount} en transfo
              </p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun lot ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
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
                    <td className="min-w-[160px] px-4 py-3">
                      <div className="h-2 rounded-full bg-[#e2ede4]">
                        <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${item.progressionPct}%` }} />
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--muted)]">{item.progressionPct}%</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5 text-xs">
                        <button className="rounded-full border border-[var(--line)] px-2.5 py-1 font-semibold text-[var(--green-700)] hover:border-[var(--green-500)]" onClick={() => openLotDetails(item)}>
                          Details
                        </button>
                        <button
                          className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]"
                          onClick={() => handleStartTransformation(item.code)}
                        >
                          Demarrer
                        </button>
                        <button className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]" onClick={() => handleAdvanceLot(item.code)}>
                          + Etape
                        </button>
                      </div>
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
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.code}</p>
                  <p className="text-xs text-[var(--muted)]">{item.produit} · {item.memberNom}</p>
                </div>
                <StatusBadge label={item.status} tone={statusTone[item.status]} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Initial</p>
                  <p className="font-semibold text-[var(--green-900)]">{item.initialQuantityKg.toLocaleString("fr-FR")} kg</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[var(--muted)]">Actuel</p>
                  <p className="font-semibold text-[var(--green-900)]">{item.currentQuantityKg.toLocaleString("fr-FR")} kg</p>
                </div>
              </div>

              <div className="mt-3 h-2 rounded-full bg-[#e2ede4]">
                <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${item.progressionPct}%` }} />
              </div>
              <p className="mt-1 text-[11px] text-[var(--muted)]">Progression {item.progressionPct}%</p>

              <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
                <button className="rounded-full border border-[var(--line)] px-2.5 py-1 font-semibold text-[var(--green-700)] hover:border-[var(--green-500)]" onClick={() => openLotDetails(item)}>
                  Details
                </button>
                <button className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]" onClick={() => handleStartTransformation(item.code)}>
                  Demarrer
                </button>
                <button className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]" onClick={() => handleAdvanceLot(item.code)}>
                  + Etape
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={openCreateModal}
        onClose={closeCreate}
        title="Creer un lot"
        subtitle="Creation locale avec generation automatique du code lot."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button className="soft-focus w-full rounded-xl border border-white/85 bg-white/55 px-4 py-2 text-sm text-[var(--green-900)] hover:bg-white/75 sm:w-auto" onClick={closeCreate} type="button">
              Annuler
            </button>
            <button className="soft-focus w-full rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)] sm:w-auto" form="lot-form" type="submit">
              Creer lot
            </button>
          </div>
        }
      >
        <form id="lot-form" onSubmit={submitCreate} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm text-[var(--muted)]">
            Date creation
            <input
              type="date"
              value={form.date}
              onChange={(event) => setForm((prev) => ({ ...prev, date: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
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

          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Membre source
            <input
              value={form.memberNom}
              onChange={(event) => setForm((prev) => ({ ...prev, memberNom: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="Ex: Awa Diop"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Quantite initiale (kg)
            <input
              type="number"
              min={1}
              value={form.initialQuantityKg}
              onChange={(event) => setForm((prev) => ({ ...prev, initialQuantityKg: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Grade dominant
            <select
              value={form.gradeDominant}
              onChange={(event) => setForm((prev) => ({ ...prev, gradeDominant: event.target.value as Grade }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {gradeFilters.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Statut initial
            <select
              value={form.status}
              onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as LotStatus }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              <option>Collecte</option>
              <option>En transformation</option>
              <option>Bloque</option>
              <option>Pret</option>
            </select>
          </label>

          {formError && <p className="sm:col-span-2 rounded-xl border border-[#ecc9c9] bg-[#fff1f1]/90 px-3 py-2 text-xs text-[#8d3d3d]">{formError}</p>}
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={Boolean(selectedLot)}
        onClose={() => setSelectedCode(null)}
        title={selectedLot ? `Detail ${selectedLot.code}` : "Detail lot"}
        subtitle={selectedLot ? `${selectedLot.produit} · ${selectedLot.memberNom}` : ""}
        size="xl"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            {selectedLot && selectedLot.status !== "Pret" && (
              <button
                className="soft-focus w-full rounded-xl border border-white/85 bg-white/55 px-4 py-2 text-sm text-[var(--green-900)] hover:bg-white/75 sm:w-auto"
                onClick={() => handleAdvanceLot(selectedLot.code)}
                type="button"
              >
                Avancer d&apos;une etape
              </button>
            )}
            <button className="soft-focus w-full rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)] sm:w-auto" onClick={() => setSelectedCode(null)} type="button">
              Fermer
            </button>
          </div>
        }
      >
        {selectedLot && (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                <p className="text-xs text-[var(--muted)]">Produit</p>
                <p className="text-sm font-semibold text-[var(--green-900)]">{selectedLot.produit}</p>
              </div>
              <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                <p className="text-xs text-[var(--muted)]">Grade dominant</p>
                <p className="text-sm font-semibold text-[var(--green-900)]">{selectedLot.gradeDominant}</p>
              </div>
              <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                <p className="text-xs text-[var(--muted)]">Membre source</p>
                <p className="text-sm font-semibold text-[var(--green-900)]">{selectedLot.memberNom}</p>
              </div>
              <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                <p className="text-xs text-[var(--muted)]">Rendement actuel</p>
                <p className="text-sm font-semibold text-[var(--green-900)]">{((selectedLot.currentQuantityKg / selectedLot.initialQuantityKg) * 100).toFixed(1)}%</p>
              </div>
            </div>

            <div className="rounded-xl border border-white/75 bg-white/52 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-[var(--green-900)]">Progression lot</p>
                <StatusBadge label={selectedLot.status} tone={statusTone[selectedLot.status]} />
              </div>
              <div className="h-2 rounded-full bg-[#dceadb]">
                <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${selectedLot.progressionPct}%` }} />
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">
                {selectedLot.progressionPct}% · {selectedLot.currentQuantityKg.toLocaleString("fr-FR")} kg / {selectedLot.initialQuantityKg.toLocaleString("fr-FR")} kg
              </p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-[var(--green-900)]">Historique etapes</h4>
              <div className="mt-2 space-y-2">
                {selectedHistory.length === 0 && <p className="rounded-xl border border-white/75 bg-white/52 px-3 py-2 text-sm text-[var(--muted)]">Aucune etape enregistree pour ce lot.</p>}
                {selectedHistory.map((step) => (
                  <div key={step.stage} className="rounded-xl border border-white/75 bg-white/52 px-3 py-2.5 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium text-[var(--green-900)]">{stageLabel[step.stage]}</p>
                      <StatusBadge label={formatStageStatus(step.state)} tone={stageTone[step.state]} />
                    </div>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      Debut: {step.startedAt} · Fin: {step.endedAt ?? "-"} · Rendement: {step.rendementPct.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </LiquidGlassModal>
    </main>
  );
}
