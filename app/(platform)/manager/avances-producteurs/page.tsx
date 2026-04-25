"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useCancelFarmerAdvance,
  useCreateFarmerAdvance,
  useFarmerAdvanceDetail,
  useFarmerAdvanceSummary,
  useUpdateFarmerAdvance,
} from "@/hooks/useFarmerAdvances";
import { useMembers } from "@/hooks/useMembers";
import type { FarmerAdvance, FarmerAdvanceCreate, FarmerAdvanceSummaryRow } from "@/lib/api/types";

type SortByField = "last_modified" | "total_amount";
type SortOrder = "asc" | "desc";

type AdvanceFormValues = {
  farmer_id: string;
  amount_fcfa: number;
  reason: string;
  advance_date: string;
  note: string;
};

function formatAmount(value: number) {
  return `${value.toLocaleString("fr-FR")} FCFA`;
}

function formatQuantity(value: number) {
  return `${value.toLocaleString("fr-FR")} kg`;
}

function formatDate(value: string) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("fr-FR");
}

function formatDateTime(value: string) {
  if (!value) return "—";
  return new Date(value).toLocaleString("fr-FR");
}

function formatCost(costPerKg?: number | null) {
  if (costPerKg === null || costPerKg === undefined) return "—";
  return `${costPerKg.toLocaleString("fr-FR")} FCFA/kg`;
}

const advanceStatusConfig: Record<string, { label: string; tone: "success" | "danger" | "info" }> = {
  active: { label: "Actif", tone: "success" },
  cancelled: { label: "Annulé", tone: "danger" },
};

export default function FarmerAdvancesPage() {
  const { data: members = [] } = useMembers();
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortByField>("last_modified");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [selectedFarmer, setSelectedFarmer] = useState<FarmerAdvanceSummaryRow | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingAdvance, setEditingAdvance] = useState<FarmerAdvance | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const summaryQuery = useFarmerAdvanceSummary({
    search,
    sort_by: sortBy,
    order: sortOrder,
  });
  const detailQuery = useFarmerAdvanceDetail(selectedFarmer?.farmer_id ?? null);

  const createAdvance = useCreateFarmerAdvance();
  const updateAdvance = useUpdateFarmerAdvance();
  const cancelAdvance = useCancelFarmerAdvance();

  const { register, handleSubmit, reset, formState } = useForm<AdvanceFormValues>({
    defaultValues: {
      farmer_id: "",
      amount_fcfa: 0,
      reason: "",
      advance_date: "",
      note: "",
    },
  });

  useEffect(() => {
    if (!formOpen && members.length > 0) {
      reset((current) => ({
        ...current,
        farmer_id: current.farmer_id || members[0].id,
      }));
    }
  }, [formOpen, members, reset]);

  const rows = summaryQuery.data?.items ?? [];
  const stats = summaryQuery.data?.stats;

  const openCreateForm = () => {
    setEditingAdvance(null);
    reset({
      farmer_id: members[0]?.id ?? "",
      amount_fcfa: 0,
      reason: "",
      advance_date: "",
      note: "",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (advance: FarmerAdvance) => {
    setEditingAdvance(advance);
    reset({
      farmer_id: advance.farmer_id,
      amount_fcfa: advance.amount_fcfa,
      reason: advance.reason,
      advance_date: advance.advance_date,
      note: advance.note ?? "",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitAdvance = handleSubmit(async (values) => {
    setFormError(null);
    const payload: FarmerAdvanceCreate = {
      farmer_id: values.farmer_id,
      amount_fcfa: Number(values.amount_fcfa),
      reason: values.reason.trim(),
      advance_date: values.advance_date,
      note: values.note.trim() || null,
    };
    try {
      if (editingAdvance) {
        await updateAdvance.mutateAsync({ id: editingAdvance.id, payload });
      } else {
        await createAdvance.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer l'avance.");
    }
  });

  const handleCancelAdvance = async (advance: FarmerAdvance) => {
    if (advance.status === "cancelled") return;
    if (!window.confirm("Annuler cette avance ? La ligne liée en trésorerie sera également annulée.")) return;
    try {
      await cancelAdvance.mutateAsync(advance.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'annuler cette avance.");
    }
  };

  return (
    <main>
      <PageIntro
        title="Avances Producteurs"
        subtitle="Suivi des avances en espèces accordées aux producteurs."
      />

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total avancé</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_advanced ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Nombre total d&apos;avances</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{(stats?.total_advances_count ?? 0).toLocaleString("fr-FR")}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Producteurs concernés</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{(stats?.affected_farmers_count ?? 0).toLocaleString("fr-FR")}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Coût moyen/kg</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatCost(stats?.average_cost_per_kg)}</p>
        </article>
      </section>

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_auto]">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
            placeholder="Rechercher un producteur..."
          />
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortByField)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="last_modified">Dernière modification</option>
            <option value="total_amount">Montant total donné</option>
          </select>
          <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>
          <button type="button" onClick={openCreateForm} className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold">
            + Nouvelle avance
          </button>
        </div>
      </section>

      {summaryQuery.isLoading ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement des avances...</p>
        </section>
      ) : summaryQuery.error ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--danger)]">{summaryQuery.error instanceof Error ? summaryQuery.error.message : "Erreur de chargement."}</p>
          <button type="button" className="soft-focus wf-btn-secondary mt-3 px-4 py-2 text-sm font-semibold" onClick={() => summaryQuery.refetch()}>
            Réessayer
          </button>
        </section>
      ) : rows.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune avance enregistrée pour le moment.</p>
          <button type="button" className="soft-focus wf-btn-primary mt-3 px-4 py-2 text-sm font-semibold" onClick={openCreateForm}>
            + Nouvelle avance
          </button>
        </section>
      ) : (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Producteur</th>
                  <th className="px-5 py-3.5">Quantité collectée totale</th>
                  <th className="px-5 py-3.5">Montant total donné</th>
                  <th className="px-5 py-3.5">Coût/kg</th>
                  <th className="px-5 py-3.5">Dernière modification</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.farmer_id}>
                    <td className="px-5 py-4 font-medium text-[var(--text)]">{row.farmer_name}</td>
                    <td className="px-5 py-4">{formatQuantity(row.total_collected_quantity)}</td>
                    <td className="px-5 py-4">{formatAmount(row.total_amount_given)}</td>
                    <td className="px-5 py-4">{formatCost(row.cost_per_kg)}</td>
                    <td className="px-5 py-4">{formatDateTime(row.last_modified)}</td>
                    <td className="px-5 py-4">
                      <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => setSelectedFarmer(row)}>
                        Voir détails
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={Boolean(selectedFarmer)}
        onClose={() => setSelectedFarmer(null)}
        title={selectedFarmer ? `Détails producteur · ${selectedFarmer.farmer_name}` : "Détails producteur"}
        subtitle="Historique des avances liées à ce producteur"
        size="xl"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" type="button" onClick={() => detailQuery.refetch()}>
              Actualiser
            </button>
            <button className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" type="button" onClick={() => setSelectedFarmer(null)}>
              Fermer
            </button>
          </div>
        }
      >
        {detailQuery.isLoading ? (
          <p className="text-sm text-[var(--muted)]">Chargement des détails...</p>
        ) : detailQuery.error ? (
          <p className="text-sm text-[var(--danger)]">{detailQuery.error instanceof Error ? detailQuery.error.message : "Erreur de chargement du détail."}</p>
        ) : detailQuery.data ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                <p className="text-xs text-[var(--muted)]">Producteur</p>
                <p className="text-sm font-semibold text-[var(--text)]">{detailQuery.data.summary.farmer_name}</p>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                <p className="text-xs text-[var(--muted)]">Quantité collectée totale</p>
                <p className="text-sm font-semibold text-[var(--text)]">{formatQuantity(detailQuery.data.summary.total_collected_quantity)}</p>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                <p className="text-xs text-[var(--muted)]">Montant total donné</p>
                <p className="text-sm font-semibold text-[var(--text)]">{formatAmount(detailQuery.data.summary.total_amount_given)}</p>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                <p className="text-xs text-[var(--muted)]">Coût/kg</p>
                <p className="text-sm font-semibold text-[var(--text)]">{formatCost(detailQuery.data.summary.cost_per_kg)}</p>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                <p className="text-xs text-[var(--muted)]">Dernière modification</p>
                <p className="text-sm font-semibold text-[var(--text)]">{formatDateTime(detailQuery.data.summary.last_modified)}</p>
              </div>
            </div>

            {detailQuery.data.advances.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">Aucune avance enregistrée pour ce producteur.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-[var(--line)]">
                <table className="wf-table min-w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Montant</th>
                      <th className="px-4 py-3">Motif</th>
                      <th className="px-4 py-3">Note</th>
                      <th className="px-4 py-3">Créé le / Modifié le</th>
                      <th className="px-4 py-3">Statut</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.advances.map((advance) => {
                      const status = advanceStatusConfig[advance.status] ?? { label: advance.status, tone: "info" as const };
                      return (
                        <tr key={advance.id}>
                          <td className="px-4 py-3">{formatDate(advance.advance_date)}</td>
                          <td className="px-4 py-3 font-medium text-[var(--text)]">{formatAmount(advance.amount_fcfa)}</td>
                          <td className="px-4 py-3">{advance.reason}</td>
                          <td className="px-4 py-3">{advance.note?.trim() ? advance.note : "—"}</td>
                          <td className="px-4 py-3 text-xs">
                            <p>{formatDateTime(advance.created_at)}</p>
                            <p className="text-[var(--muted)]">{formatDateTime(advance.updated_at)}</p>
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge label={status.label} tone={status.tone} />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditForm(advance)} disabled={advance.status === "cancelled"}>
                                Modifier
                              </button>
                              <button
                                className="text-xs font-semibold text-[var(--danger)] hover:underline disabled:opacity-40"
                                onClick={() => handleCancelAdvance(advance)}
                                disabled={advance.status === "cancelled" || cancelAdvance.isPending}
                              >
                                Annuler
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">Aucun détail disponible.</p>
        )}
      </LiquidGlassModal>

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingAdvance ? "Modifier avance" : "Nouvelle avance"}
        subtitle="L'enregistrement crée automatiquement une ligne de dépense en trésorerie."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="advance-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="advance-form" onSubmit={submitAdvance} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Producteur
            <select {...register("farmer_id", { required: "Producteur requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="" disabled>
                Sélectionner un producteur
              </option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Montant (FCFA)
            <input
              type="number"
              step="0.01"
              min="0"
              {...register("amount_fcfa", { required: "Montant requis.", valueAsNumber: true, min: 0.01 })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="50000"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Motif
            <input
              {...register("reason", { required: "Motif requis." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="Préfinancement campagne"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...register("advance_date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Note
            <textarea {...register("note")} className="wf-input mt-2 min-h-[96px] w-full px-3 py-2 text-sm" placeholder="Commentaire optionnel..." />
          </label>

          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>

      {formError && !formOpen && (
        <section className="mt-4 rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
          {formError}
        </section>
      )}
    </main>
  );
}
