"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useCancelTreasuryTransaction,
  useCreateTreasuryTransaction,
  useTreasuryStats,
  useTreasuryTransactions,
  useUpdateTreasuryTransaction,
} from "@/hooks/useTreasury";
import type {
  TreasuryTransaction,
  TreasuryTransactionCreate,
  TreasuryTransactionType,
} from "@/lib/api/types";

type FilterType = "all" | "income" | "expense";
type SortOrder = "asc" | "desc";

type TreasuryFormValues = {
  transaction_date: string;
  type: TreasuryTransactionType;
  category: string;
  label: string;
  amount_fcfa: number;
  note: string;
  source_type: string;
};

const typeBadge: Record<TreasuryTransactionType, { label: string; tone: "success" | "danger" }> = {
  income: { label: "Recette", tone: "success" },
  expense: { label: "Dépense", tone: "danger" },
};

const statusBadge: Record<string, { label: string; tone: "success" | "danger" | "info" }> = {
  recorded: { label: "Enregistré", tone: "success" },
  cancelled: { label: "Annulé", tone: "danger" },
};

function formatAmount(value: number) {
  return `${value.toLocaleString("fr-FR")} FCFA`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("fr-FR");
}

function sourceLabel(sourceType: string) {
  if (sourceType === "farmer_advance") return "Avance producteur";
  if (sourceType === "management") return "Gestion";
  if (sourceType === "manual") return "Manuel";
  return "Manuel / autre";
}

function formatExportDate(value: Date) {
  return value.toLocaleString("fr-FR");
}

export default function TreasuryPage() {
  const [typeFilter, setTypeFilter] = useState<FilterType>("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "farmer_advance" | "management" | "manual">("all");
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [formOpen, setFormOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<TreasuryTransaction | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const transactionsQuery = useTreasuryTransactions({
    type: typeFilter,
    source_type: sourceFilter,
    search,
    sort: sortOrder,
  });
  const statsQuery = useTreasuryStats();

  const createTransaction = useCreateTreasuryTransaction();
  const updateTransaction = useUpdateTreasuryTransaction();
  const cancelTransaction = useCancelTreasuryTransaction();

  const { register, handleSubmit, reset, formState } = useForm<TreasuryFormValues>({
    defaultValues: {
      transaction_date: "",
      type: "expense",
      category: "autre",
      label: "",
      amount_fcfa: 0,
      note: "",
      source_type: "manual",
    },
  });

  const transactions = transactionsQuery.data ?? [];
  const stats = statsQuery.data;

  const openCreateForm = () => {
    setEditingTransaction(null);
    reset({
      transaction_date: "",
      type: "expense",
      category: "autre",
      label: "",
      amount_fcfa: 0,
      note: "",
      source_type: "manual",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (transaction: TreasuryTransaction) => {
    setEditingTransaction(transaction);
    reset({
      transaction_date: transaction.transaction_date,
      type: transaction.type,
      category: transaction.category,
      label: transaction.label,
      amount_fcfa: transaction.amount_fcfa,
      note: transaction.note ?? "",
      source_type: transaction.source_type || "manual",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitTransaction = handleSubmit(async (values) => {
    setFormError(null);
    const payload: TreasuryTransactionCreate = {
      transaction_date: values.transaction_date,
      type: values.type,
      category: values.category.trim(),
      label: values.label.trim(),
      amount_fcfa: Number(values.amount_fcfa),
      note: values.note.trim() || null,
      source_type: values.source_type,
    };

    try {
      if (editingTransaction) {
        await updateTransaction.mutateAsync({ id: editingTransaction.id, payload });
      } else {
        await createTransaction.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer la transaction.");
    }
  });

  const handleCancelTransaction = async (transaction: TreasuryTransaction) => {
    if (transaction.status === "cancelled") return;
    if (!window.confirm("Annuler cette transaction ?")) return;
    try {
      await cancelTransaction.mutateAsync(transaction.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'annuler cette transaction.");
    }
  };

  const exportPdf = () => {
    const now = new Date();
    const visibleRows = transactions
      .map((transaction) => {
        const type = typeBadge[transaction.type]?.label ?? transaction.type;
        const status = statusBadge[transaction.status]?.label ?? transaction.status;
        return `
          <tr>
            <td>${transaction.reference}</td>
            <td>${formatDate(transaction.transaction_date)}</td>
            <td>${type}</td>
            <td>${transaction.category}</td>
            <td>${transaction.label}</td>
            <td>${formatAmount(transaction.amount_fcfa)}</td>
            <td>${sourceLabel(transaction.source_type)}</td>
            <td>${status}</td>
          </tr>
        `;
      })
      .join("");

    const html = `
      <!doctype html>
      <html lang="fr">
        <head>
          <meta charset="utf-8" />
          <title>Rapport de trésorerie</title>
          <style>
            body { font-family: Arial, sans-serif; color: #1d2a24; padding: 24px; }
            h1 { margin: 0 0 8px; color: #0d5a2b; }
            .meta { margin-bottom: 16px; font-size: 12px; color: #44554c; }
            .kpis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
            .kpi { border: 1px solid #d8e6dc; border-radius: 8px; padding: 8px; font-size: 12px; }
            .kpi b { display: block; margin-top: 4px; font-size: 14px; color: #0f3b25; }
            table { width: 100%; border-collapse: collapse; font-size: 12px; }
            th, td { border: 1px solid #dbe8df; padding: 8px; text-align: left; }
            th { background: #eef7f1; color: #1f4d33; }
          </style>
        </head>
        <body>
          <h1>Rapport de trésorerie</h1>
          <div class="meta">Date d'export: ${formatExportDate(now)}</div>
          <div class="kpis">
            <div class="kpi">Total donné<b>${formatAmount(stats?.total_given ?? 0)}</b></div>
            <div class="kpi">Total dépenses<b>${formatAmount(stats?.total_expenses ?? 0)}</b></div>
            <div class="kpi">Total recettes<b>${formatAmount(stats?.total_income ?? 0)}</b></div>
            <div class="kpi">Solde actuel<b>${formatAmount(stats?.current_balance ?? 0)}</b></div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Référence</th><th>Date</th><th>Type</th><th>Catégorie</th><th>Libellé</th><th>Montant</th><th>Source</th><th>Statut</th>
              </tr>
            </thead>
            <tbody>${visibleRows || '<tr><td colspan="8">Aucune donnée</td></tr>'}</tbody>
          </table>
        </body>
      </html>
    `;

    const printWindow = window.open("", "_blank", "noopener,noreferrer,width=1100,height=900");
    if (!printWindow) return;
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  return (
    <main>
      <PageIntro title="Trésorerie" />

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total donné</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_given ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total dépenses</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_expenses ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total recettes</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_income ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Solde actuel</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.current_balance ?? 0)}</p>
        </article>
      </section>

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as FilterType)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="all">Tous types</option>
            <option value="income">Recette</option>
            <option value="expense">Dépense</option>
          </select>

          <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="all">Toutes sources</option>
            <option value="farmer_advance">Avance producteur</option>
            <option value="management">Gestion</option>
            <option value="manual">Manuel / autre</option>
          </select>

          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
            placeholder="Rechercher libellé ou producteur..."
          />

          <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="desc">Date desc</option>
            <option value="asc">Date asc</option>
          </select>

          <button type="button" onClick={openCreateForm} className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold">
            + Nouvelle transaction
          </button>
          <button type="button" onClick={exportPdf} className="soft-focus rounded-xl border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)]">
            Export PDF
          </button>
        </div>
      </section>

      {transactionsQuery.isLoading ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement de la trésorerie...</p>
        </section>
      ) : transactionsQuery.error ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--danger)]">{transactionsQuery.error instanceof Error ? transactionsQuery.error.message : "Erreur de chargement."}</p>
          <button type="button" className="soft-focus wf-btn-secondary mt-3 px-4 py-2 text-sm font-semibold" onClick={() => transactionsQuery.refetch()}>
            Réessayer
          </button>
        </section>
      ) : transactions.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune transaction enregistrée pour le moment.</p>
          <button type="button" className="soft-focus wf-btn-primary mt-3 px-4 py-2 text-sm font-semibold" onClick={openCreateForm}>
            + Nouvelle transaction
          </button>
        </section>
      ) : (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Référence</th>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Catégorie</th>
                  <th className="px-5 py-3.5">Libellé</th>
                  <th className="px-5 py-3.5">Montant</th>
                  <th className="px-5 py-3.5">Source</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const type = typeBadge[transaction.type] ?? { label: transaction.type, tone: "danger" as const };
                  const status = statusBadge[transaction.status] ?? { label: transaction.status, tone: "info" as const };
                  const isFarmerAdvance = transaction.source_type === "farmer_advance";

                  return (
                    <tr key={transaction.id}>
                      <td className="px-5 py-4 font-medium text-[var(--text)]">{transaction.reference}</td>
                      <td className="px-5 py-4">{formatDate(transaction.transaction_date)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={type.label} tone={type.tone} />
                      </td>
                      <td className="px-5 py-4">{transaction.category}</td>
                      <td className="px-5 py-4">
                        <p>{transaction.label}</p>
                        {transaction.farmer_name ? <p className="text-xs text-[var(--muted)]">{transaction.farmer_name}</p> : null}
                      </td>
                      <td className="px-5 py-4">{formatAmount(transaction.amount_fcfa)}</td>
                      <td className="px-5 py-4">{sourceLabel(transaction.source_type)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={status.label} tone={status.tone} />
                      </td>
                      <td className="px-5 py-4">
                        {isFarmerAdvance ? (
                          <span className="text-xs text-[var(--muted)]">Géré via avances</span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditForm(transaction)} disabled={transaction.status === "cancelled"}>
                              Modifier
                            </button>
                            <button
                              className="text-xs font-semibold text-[var(--danger)] hover:underline disabled:opacity-40"
                              onClick={() => handleCancelTransaction(transaction)}
                              disabled={transaction.status === "cancelled" || cancelTransaction.isPending}
                            >
                              Annuler
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingTransaction ? "Modifier transaction" : "Nouvelle transaction"}
        subtitle="Transaction manuelle hors avances producteurs."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="treasury-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="treasury-form" onSubmit={submitTransaction} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...register("transaction_date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Type
              <select {...register("type", { required: "Type requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="expense">Dépense</option>
                <option value="income">Recette</option>
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Source
              <select {...register("source_type", { required: "Source requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="manual">Manuel</option>
                <option value="management">Gestion</option>
                <option value="other">Autre</option>
              </select>
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Catégorie
              <select {...register("category", { required: "Catégorie requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="gestion">gestion</option>
                <option value="administration">administration</option>
                <option value="transport">transport</option>
                <option value="operation">opération</option>
                <option value="autre">autre</option>
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
                placeholder="25000"
              />
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Libellé
            <input {...register("label", { required: "Libellé requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="Transport vers entrepôt" />
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
    </main>
  );
}
